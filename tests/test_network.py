"""Network filtering regressions; fixtures use documentation-only addresses."""
import subprocess
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extension'))
from vbox_network import (
    AdapterAddress, collect_snapshot, connected_adapters, legacy_rows,
    match_guest_addresses, normalize_mac, rows_from_payload,
)

VM_INFO = '''nic1="nat"
macaddress1="080027AABB01"
cableconnected1="on"
nic2="hostonly"
macaddress2="080027AABB02"
cableconnected2="on"
nic3="bridged"
macaddress3="080027AABB03"
cableconnected3="off"
nic4="none"
macaddress4="080027AABB04"
cableconnected4="on"
'''


def properties(interfaces):
    """Encode guest interface fixtures in VBoxManage's --old-format output."""
    return '\n'.join(
        f'Name: /VirtualBox/GuestInfo/Net/{index}/{field}, value: {value}, '
        'timestamp: 123456789, flags:'
        for index, fields in interfaces.items() for field, value in fields.items()
    )


class NetworkTests(unittest.TestCase):
    def test_mac_matching_ignores_docker_and_interface_index_order(self):
        guest = properties({
            0: {'Name': 'docker0', 'MAC': '0242AC110001', 'Status': 'Up', 'V4/IP': '172.17.0.1'},
            7: {'Name': 'enp0s8', 'MAC': '08:00:27:aa:bb:02', 'Status': 'Up', 'V4/IP': '198.51.100.11'},
            3: {'Name': 'enp0s3', 'MAC': '080027AABB01', 'Status': 'Up', 'V4/IP': '192.0.2.10'},
            9: {'Name': 'br-example', 'MAC': '0242AC120001', 'Status': 'Up', 'V4/IP': '172.18.0.1'},
        })
        self.assertEqual(match_guest_addresses('Example VM', VM_INFO, guest), [
            AdapterAddress('Example VM', 'enp0s3', '192.0.2.10'),
            AdapterAddress('Example VM', 'enp0s8', '198.51.100.11'),
        ])

    def test_disabled_unplugged_and_guest_down_interfaces_are_excluded(self):
        guest = properties({
            0: {'MAC': '080027AABB01', 'Status': 'Down', 'V4/IP': '192.0.2.10'},
            1: {'MAC': '080027AABB03', 'Status': 'Up', 'V4/IP': '192.0.2.11'},
            2: {'MAC': '080027AABB04', 'Status': 'Up', 'V4/IP': '192.0.2.12'},
        })
        self.assertEqual(match_guest_addresses('Example', VM_INFO, guest), [])
        self.assertEqual(connected_adapters(VM_INFO.replace('nic1="nat"', 'nic1="null"'))[0].slot, 2)

    def test_addresses_are_separate_normalized_and_deduplicated(self):
        guest = properties({5: {
            'Name': 'enp0s3', 'MAC': '080027AABB01', 'Status': 'Up',
            'V4/IP': '192.0.2.10', 'V4/IP/0': '192.0.2.10',
            'V6/IP': '2001:0db8::10', 'V6/IP/1': 'fe80::1',
            'V6/IP/2': '::1', 'V6/IP/3': 'ff02::1', 'V4/IP/1': '0.0.0.0',
            'V4/IP/2': '169.254.1.2', 'V4/IP/3': 'invalid',
        }})
        self.assertEqual([row.ip for row in match_guest_addresses('VM', VM_INFO, guest)],
                         ['192.0.2.10', '2001:db8::10'])

    def test_missing_name_uses_vm_slot_and_missing_mac_is_not_guessed(self):
        guest = properties({
            0: {'Status': 'Up', 'V4/IP': '192.0.2.99'},
            8: {'MAC': '080027AABB02', 'V4/IP': '198.51.100.11'},
        })
        self.assertEqual(match_guest_addresses('VM', VM_INFO, guest),
                         [AdapterAddress('VM', 'Adapter 2', '198.51.100.11')])

    def test_duplicate_configured_macs_are_ambiguous(self):
        guest = properties({0: {'MAC': '080027AABB01', 'V4/IP': '192.0.2.10'}})
        info = VM_INFO.replace('080027AABB02', '080027AABB01')
        self.assertEqual(match_guest_addresses('VM', info, guest), [])

    def test_matching_does_not_depend_on_interface_name_heuristics(self):
        guest = properties({0: {'Name': 'br0', 'MAC': '080027AABB01', 'V4/IP': '192.0.2.10'}})
        self.assertEqual(match_guest_addresses('VM', VM_INFO, guest)[0].adapter, 'br0')

    def test_no_running_vms_does_not_query_saved_files_or_other_commands(self):
        calls = []
        def query(*arguments):
            calls.append(arguments)
            return ''
        snapshot = collect_snapshot(query)
        self.assertEqual(snapshot.rows, ())
        self.assertEqual(calls, [('list', 'runningvms')])

    def test_one_failed_vm_does_not_hide_another_vm(self):
        def query(*arguments):
            if arguments == ('list', 'runningvms'):
                return '"Unavailable VM" {00000000-0000-0000-0000-000000000001}\n"Working VM" {00000000-0000-0000-0000-000000000002}\n'
            if arguments[1] == '00000000-0000-0000-0000-000000000001':
                raise subprocess.TimeoutExpired('VBoxManage', 8)
            if arguments[0] == 'showvminfo':
                return VM_INFO
            return properties({0: {'Name': 'enp0s3', 'MAC': '080027AABB01', 'V4/IP': '192.0.2.10'}})
        snapshot = collect_snapshot(query)
        self.assertEqual(snapshot.rows, (AdapterAddress('Working VM', 'enp0s3', '192.0.2.10'),))
        self.assertEqual(len(snapshot.warnings), 1)

    def test_query_failure_is_explicit(self):
        def query(*_arguments):
            raise FileNotFoundError('VBoxManage')
        snapshot = collect_snapshot(query)
        self.assertFalse(snapshot.rows)
        self.assertTrue(snapshot.warnings)

    def test_panel_contract_and_legacy_protocol(self):
        rows = [AdapterAddress('VM', 'enp0s3', '192.0.2.10'),
                AdapterAddress('VM', 'enp0s8', '198.51.100.11')]
        self.assertEqual(rows_from_payload([row.to_dict() for row in rows]), rows)
        self.assertEqual(legacy_rows(rows), [('VM', '192.0.2.10, 198.51.100.11')])
        for invalid in [None, {}, [{'vm': 'VM'}], [{'vm': 'VM', 'adapter': 'eth0', 'ip': 'invalid'}]]:
            with self.assertRaises(ValueError):
                rows_from_payload(invalid)

    def test_mac_normalization_rejects_invalid_or_unknown_macs(self):
        self.assertEqual(normalize_mac('08-00-27-aa-bb-01'), '080027AABB01')
        self.assertIsNone(normalize_mac('000000000000'))
        self.assertIsNone(normalize_mac('not-a-mac'))


if __name__ == '__main__':
    unittest.main()
