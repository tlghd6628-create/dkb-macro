"""The market section is closed for now. Settings logic only, not a game test."""
import unittest

import bootstrap  # noqa: F401
import owner_settings_console as console
from owner_settings_layout import consolidated


class Closed(unittest.TestCase):
    def test_every_market_key_and_nothing_else(self):
        self.assertTrue(console.closed('auto_register.market.enabled'))
        self.assertTrue(console.closed('auto_register.market.final_adjustment'))
        self.assertTrue(console.closed('auto_register.market.bag.enabled'))
        self.assertFalse(console.closed('auto_register.equipment_disassembly.enabled'))
        self.assertFalse(console.closed('auto_rewards.mail.enabled'))

    def test_bag_no_longer_defaults_on(self):
        schema = {'tabs': [{'groups': [{'fields': [{'id': 'auto_register.market.bag.enabled', 'type': 'checkbox', 'default': True}]}]}]}
        self.assertIs(consolidated(schema)['tabs'][0]['groups'][0]['fields'][0]['default'], False)


if __name__ == '__main__':
    unittest.main()
