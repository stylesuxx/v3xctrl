"""
Manages adaptive QP (Quantization Parameter) adjustment based on I-frame sizes.

Adjusts the minimum QP value to keep I-frame sizes within a target range,
helping control bandwidth spikes during scene changes.
"""
import logging

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst


class QPManager:
    def __init__(
        self,
        encoder: Gst.Element,
        max_i_frame_bytes: int,
        qp_min: int,
        qp_max: int,
        min_step: int = 1,
        max_step: int = 5,
        cooldown_keyframes: int = 0,
        lower_limit_percent: float = 0.85
    ) -> None:
        self._encoder = encoder

        self._max_i_frame_bytes = max_i_frame_bytes
        self._min_i_frame_bytes = max_i_frame_bytes * lower_limit_percent
        self._target_i_frame_bytes = (max_i_frame_bytes + self._min_i_frame_bytes) / 2

        self._qp_min_limit = qp_min
        self._qp_max_limit = qp_max
        self._current_qp_min = qp_min

        self._min_step = min_step
        self._max_step = max_step
        self._cooldown_keyframes = cooldown_keyframes
        self._keyframes_since_adjust = 0

    @property
    def current_qp_min(self) -> int:
        return self._current_qp_min

    @property
    def qp_max(self) -> int:
        return self._qp_max_limit

    def on_keyframe(self, size: int) -> None:
        """
        Called for each keyframe (I-frame). Adjusts QP if size is outside target range.

        Args:
            size: Keyframe size in bytes
        """
        self._keyframes_since_adjust += 1
        if self._keyframes_since_adjust > self._cooldown_keyframes:
            self._adjust(size)
            self._keyframes_since_adjust = 0

    def _adjust(self, i_frame_size: int) -> None:
        """
        Adjust minimum QP based on I-frame size.

        Args:
            i_frame_size: Size of the I-frame in bytes
        """
        if self._min_i_frame_bytes <= i_frame_size <= self._max_i_frame_bytes:
            return

        size_ratio = i_frame_size / self._target_i_frame_bytes

        calculated_step = int(size_ratio)
        step_size = min(max(calculated_step, self._min_step), self._max_step)

        new_qp_min = self._current_qp_min

        if i_frame_size > self._max_i_frame_bytes:
            new_qp_min = min(self._current_qp_min + step_size, self._qp_max_limit)

        elif i_frame_size < self._min_i_frame_bytes:
            new_qp_min = max(self._current_qp_min - step_size, self._qp_min_limit)

        if new_qp_min != self._current_qp_min:
            self._current_qp_min = new_qp_min
            self._apply_qp()

    def _apply_qp(self) -> None:
        """Apply the current QP settings to the encoder."""
        try:
            encoder_controls = (
                f"controls,"
                f"h264_minimum_qp_value={self._current_qp_min},"
                f"h264_maximum_qp_value={self._qp_max_limit}"
            )

            self._encoder.set_property(
                "extra-controls",
                Gst.Structure.from_string(encoder_controls)[0]
            )

            logging.info("QP min set to %d", self._current_qp_min)

        except Exception as e:
            logging.error("Failed to adjust QP: %s", e)
