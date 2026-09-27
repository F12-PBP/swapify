def _use_light_text(hex_color):
    """Choose the higher-contrast label color for a color swatch."""
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    luminance = sum(
        channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722))
    )
    return (1.05 / (luminance + 0.05)) > ((luminance + 0.05) / 0.05)
