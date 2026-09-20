import unittest

from core.audio_devices import (
    HEADPHONES,
    OTHER,
    SPEAKERS,
    classify_audio_output,
    headphones_were_disconnected,
    output_kind_label,
)


class AudioDeviceTests(unittest.TestCase):
    def test_detects_common_headphone_names(self):
        for name in (
            "Headphones (Realtek(R) Audio)",
            "WH-1000XM5 Headset",
            "Apple AirPods Pro",
            "Galaxy Buds2 Pro",
            "USB Earphones",
        ):
            with self.subTest(name=name):
                self.assertEqual(classify_audio_output(name), HEADPHONES)

    def test_detects_common_speaker_names(self):
        for name in (
            "Speakers (Realtek(R) Audio)",
            "NVIDIA High Definition Audio (HDMI)",
            "USB Line Out",
        ):
            with self.subTest(name=name):
                self.assertEqual(classify_audio_output(name), SPEAKERS)

    def test_unknown_and_empty_outputs_are_safe(self):
        self.assertEqual(classify_audio_output("USB DAC"), OTHER)
        self.assertEqual(classify_audio_output(None), OTHER)
        self.assertEqual(output_kind_label(OTHER), "Audio output")

    def test_only_transition_away_from_headphones_counts_as_disconnect(self):
        self.assertTrue(headphones_were_disconnected(HEADPHONES, SPEAKERS))
        self.assertTrue(headphones_were_disconnected(HEADPHONES, OTHER))
        self.assertFalse(headphones_were_disconnected(SPEAKERS, HEADPHONES))
        self.assertFalse(headphones_were_disconnected(HEADPHONES, HEADPHONES))


if __name__ == "__main__":
    unittest.main()
