"""One mapping between persisted clothing types and onboarding style preferences."""

CATEGORIES = (
    ("top", "tops", "Tops"),
    ("bottom", "bottoms", "Bottoms"),
    ("dress", "dresses", "Dresses"),
    ("outerwear", "outerwear", "Outerwear"),
    ("footwear", "shoes", "Shoes"),
    ("bag", "bags", "Bags"),
    ("accessory", "accessories", "Accessories"),
)
STYLE_CHOICES = tuple((style, label) for _, style, label in CATEGORIES)
STYLE_TO_TYPE = {style: clothing_type for clothing_type, style, _ in CATEGORIES}
DISCOVERY_TYPES = tuple((value, label) for value, _, label in CATEGORIES)
