"""Read current guest IPs and match them to VirtualBox virtual network cards.

Guest Additions enumerate *guest interfaces*, including Docker bridges. Those
indices are unrelated to the slots in VirtualBox's VM settings. Match by MAC
address instead, and only accept enabled cards with their virtual cable attached.
This module has no GTK dependency and never modifies a VM or guest property.
"""
from dataclasses import asdict, dataclass
import ipaddress
import os
import re
import subprocess
from collections.abc import Callable, Iterable

MACHINE_PATTERN = re.compile(r'^"(.*)"\s+\{([0-9a-fA-F-]+)\}\s*$', re.MULTILINE)
PROPERTY_PATTERN = re.compile(
    r'^Name: /VirtualBox/GuestInfo/Net/(?P<index>\d+)/(?P<field>[^,]+), '
    r'value: (?P<value>.*?), timestamp:', re.MULTILINE,
)
ADDRESS_FIELD = re.compile(r'V[46]/IP(?:/\d+)?$')
COMMAND_TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class AdapterAddress:
    """One copyable address belonging to one VM network adapter."""

    vm: str
    adapter: str
    ip: str

    def to_dict(self) -> dict[str, str]:
        """Return the documented --adapter-json wire format."""
        return asdict(self)


@dataclass(frozen=True)
class VirtualAdapter:
    """An enabled, cable-connected card from VM settings; slots start at 1."""

    slot: int
    mac: str


@dataclass(frozen=True)
class NetworkSnapshot:
    """A live query result; failures of individual VMs do not discard other VMs."""

    rows: tuple[AdapterAddress, ...]
    warnings: tuple[str, ...] = ()


def run_vbox(*arguments: str) -> str:
    """Run a read-only VBoxManage query with stable English output and a deadline."""
    return subprocess.run(
        ['VBoxManage', *arguments], capture_output=True, text=True,
        timeout=COMMAND_TIMEOUT_SECONDS, check=True,
        env={**os.environ, 'LC_ALL': 'C'},
    ).stdout


def normalize_mac(value: str) -> str | None:
    """Accept compact, colon-separated, or hyphen-separated Ethernet MACs."""
    compact = value.strip().replace(':', '').replace('-', '').upper()
    if re.fullmatch(r'[0-9A-F]{12}', compact) and compact != '000000000000':
        return compact
    return None


def usable_address(value: str) -> str | None:
    """Normalize unicast IPs; omit loopback, unspecified, and link-local IPs."""
    try:
        address = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if (address.is_loopback or address.is_unspecified or address.is_multicast
            or address.is_link_local):
        return None
    return str(address)


def connected_adapters(machine_info: str) -> list[VirtualAdapter]:
    """Parse NIC settings without assuming guest-interface index == NIC slot.

    `nicN="none"` means disabled; `null` means not attached to a network.
    Require cableconnectedN="on" rather than assuming that a missing value is on.
    """
    settings = {}
    for line in machine_info.splitlines():
        key, separator, value = line.partition('=')
        if separator:
            settings[key.strip()] = value.strip().strip('"')
    adapters = []
    for key, mode in settings.items():
        match = re.fullmatch(r'nic(\d+)', key)
        if not match or mode in ('none', 'null', ''):
            continue
        slot = int(match[1])
        mac = normalize_mac(settings.get(f'macaddress{slot}', ''))
        if mac and settings.get(f'cableconnected{slot}') == 'on':
            adapters.append(VirtualAdapter(slot, mac))
    return sorted(adapters, key=lambda adapter: adapter.slot)


def match_guest_addresses(vm: str, machine_info: str, properties: str) -> list[AdapterAddress]:
    """Join guest interfaces to VM cards by MAC and return distinct adapter/IP rows.

    A missing Name is safe: display the matched VirtualBox slot. A missing MAC
    is not safe: omit that interface instead of guessing, which could expose a
    Docker IP as the VM's IP. Explicitly down interfaces are also excluded.
    """
    interfaces: dict[int, dict[str, str]] = {}
    for match in PROPERTY_PATTERN.finditer(properties):
        interfaces.setdefault(int(match['index']), {})[match['field']] = match['value']

    adapters = connected_adapters(machine_info)
    rows = []
    seen: set[tuple[int, str]] = set()
    for adapter in adapters:
        # Duplicate MACs in VM settings cannot identify a card unambiguously.
        if sum(card.mac == adapter.mac for card in adapters) != 1:
            continue
        for fields in interfaces.values():
            if normalize_mac(fields.get('MAC', '')) != adapter.mac:
                continue
            status = fields.get('Status', '').strip().lower()
            if status and status != 'up':
                continue
            name = fields.get('Name', '').strip() or f'Adapter {adapter.slot}'
            addresses = {
                address for field, value in fields.items()
                if ADDRESS_FIELD.fullmatch(field) and (address := usable_address(value))
            }
            for address in sorted(addresses, key=lambda ip: (ipaddress.ip_address(ip).version,
                                                             int(ipaddress.ip_address(ip)))):
                identity = adapter.slot, address
                if identity not in seen:
                    rows.append(AdapterAddress(vm, name, address))
                    seen.add(identity)
    return rows


def collect_snapshot(query: Callable[..., str] = run_vbox) -> NetworkSnapshot:
    """Query running VMs only; never infer running state or IPs from old log files."""
    try:
        machines = MACHINE_PATTERN.findall(query('list', 'runningvms'))
    except (OSError, subprocess.SubprocessError):
        return NetworkSnapshot((), ('Could not query running VirtualBox VMs.',))
    rows = []
    warnings = []
    for name, machine_id in machines:
        try:
            info = query('showvminfo', machine_id, '--machinereadable')
            properties = query('guestproperty', 'enumerate', machine_id, '--old-format')
            rows.extend(match_guest_addresses(name, info, properties))
        except (OSError, subprocess.SubprocessError):
            warnings.append(f'Could not read current network information for {name}.')
    return NetworkSnapshot(tuple(rows), tuple(warnings))


def legacy_rows(rows: Iterable[AdapterAddress]) -> list[tuple[str, str]]:
    """Keep --json compatible with a GNOME extension loaded before this update."""
    machines: dict[str, list[str]] = {}
    for row in rows:
        addresses = machines.setdefault(row.vm, [])
        if row.ip not in addresses:
            addresses.append(row.ip)
    return [(name, ', '.join(addresses)) for name, addresses in machines.items()]


def rows_from_payload(payload: list[dict[str, str]]) -> list[AdapterAddress]:
    """Validate a panel snapshot before rendering it as plain, non-markup labels."""
    if not isinstance(payload, list):
        raise ValueError('Expected a JSON array of adapter addresses.')
    rows = []
    for item in payload:
        if not isinstance(item, dict) or any(not isinstance(item.get(key), str)
                                             for key in ('vm', 'adapter', 'ip')):
            raise ValueError('Each row must contain VM, adapter, and IP strings.')
        address = usable_address(item['ip'])
        if address is None:
            raise ValueError('The panel snapshot contains an invalid IP address.')
        rows.append(AdapterAddress(item['vm'], item['adapter'], address))
    return rows
