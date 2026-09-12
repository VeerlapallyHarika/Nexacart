from typing import Dict, Any, List, Optional, Tuple
import re
from sqlalchemy.orm import Session
from services.product_service import (
    ATTRIBUTE_ALIASES,
    BOOLEAN_ALIASES,
    STRING_ALIASES,
    SearchConstraint,
    ProductService,
)
from services.category_matcher import match_category_from_message


class IntentService:
    """Extract structured shopping intent from natural-language messages.

    This is a generic, category-agnostic intent extractor. It does NOT contain
    hardcoded category lists or attribute mappings beyond what is defined in
    PRODUCT_ATTRIBUTE_ALIASES.
    """

    @staticmethod
    def extract_intent(message: str, db: Optional[Session] = None) -> Dict[str, Any]:
        """Extract a structured intent dictionary from a user message.

        Returns:
            {
                "category": str | None,
                "max_price": float | None,
                "min_price": float | None,
                "brand": str | None,
                "constraints": [SearchConstraint, ...],
                "raw_message": str,
            }
        """
        message_lower = message.lower().strip()

        category = None
        if db:
            category = IntentService._resolve_category_from_db(db, message_lower)

        max_price = IntentService._extract_max_price(message_lower)
        min_price = IntentService._extract_min_price(message_lower)
        brand = IntentService._extract_brand(message_lower)
        constraints = IntentService._extract_constraints(message_lower)

        return {
            "category": category,
            "max_price": max_price,
            "min_price": min_price,
            "brand": brand,
            "constraints": constraints,
            "raw_message": message,
        }

    @staticmethod
    def extract_legacy_intent(message: str) -> Dict[str, Any]:
        """Legacy interface — returns the old 4-field format for backward compatibility."""
        intent = IntentService.extract_intent(message)
        constraints = intent.get("constraints", [])
        battery = None
        anc = None
        for c in constraints:
            if c.key == "battery_life_hours" and c.operator == "gte":
                battery = int(c.value) if c.value else None
            elif c.key == "noise_cancellation" and c.operator == "eq":
                anc = c.value
        return {
            "category": intent["category"],
            "max_price": intent["max_price"],
            "min_battery_life": battery,
            "noise_cancellation": anc,
        }

    @staticmethod
    def _resolve_category_from_db(db: Session, message: str) -> Optional[str]:
        """Resolve category by matching user message tokens against DB categories.

        Delegates to the shared category_matcher module for generic linguistic
        matching (singularization, suffix matching, synonym expansion).
        """
        db_categories = ProductService.get_all_categories(db)
        if not db_categories:
            return None

        return match_category_from_message(message, db_categories)

    @staticmethod
    def _extract_max_price(message: str) -> Optional[float]:
        """Extract maximum price from message. Supports multiple formats."""
        patterns = [
            (r"under\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", False),
            (r"below\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", False),
            (r"less\s+than\s+₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", False),
            (r"max(?:imum)?\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", False),
            (r"budget\s*(?:of|is|:)?\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", False),
            (r"₹\s*(\d+(?:,\d{3})*(?:\.\d+)?)", False),
            (r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:rupees|inr)", False),
            (r"(\d+(?:,\d{3})*)\s*k(?:\s|$)", True),
        ]

        for pattern, is_k_pattern in patterns:
            match = re.search(pattern, message)
            if match:
                price_str = match.group(1).replace(",", "")
                if is_k_pattern:
                    return float(price_str) * 1000
                return float(price_str)

        return None

    @staticmethod
    def _extract_min_price(message: str) -> Optional[float]:
        """Extract minimum price from message."""
        patterns = [
            (r"above\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", False),
            (r"over\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", False),
            (r"more\s+than\s+₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", False),
            (r"min(?:imum)?\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", False),
            (r"starting\s+(?:from|at)\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)", False),
            (r"between\s*₹?\s*(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:to|-|and)\s*₹?\s*\d+", False),
        ]

        for pattern, is_k_pattern in patterns:
            match = re.search(pattern, message)
            if match:
                price_str = match.group(1).replace(",", "")
                if is_k_pattern:
                    return float(price_str) * 1000
                return float(price_str)

        return None

    @staticmethod
    def _extract_brand(message: str) -> Optional[str]:
        """Extract brand name from message."""
        known_brands = [
            "samsung", "apple", "sony", "jbl", "bose", "lg", "hp", "dell",
            "lenovo", "asus", "acer", "oneplus", "xiaomi", "redmi", "realme",
            "google", "nokia", "motorola", "nothing", "poco", "vivo", "oppo",
            "boat", "noise", "amazfit", "fossil", "garmin", "marshall",
            "logitech", "razer", "keychron", "cosmic byte", "redgear",
            "hisense", "tcl", "canonical", "nikon", "fujifilm", "panasonic",
            "adidas", "nike", "puma",
        ]

        message_lower = message.lower()
        for brand in known_brands:
            if brand in message_lower:
                return brand.title()

        return None

    @staticmethod
    def _extract_constraints(message: str) -> List[SearchConstraint]:
        """Extract attribute constraints from the message generically.

        Looks for patterns like:
        - "16GB RAM" → ram_gb >= 16
        - "50MP camera" → camera_mp >= 50
        - "wireless" → wireless = True
        - "with noise cancellation" → noise_cancellation = True
        - "4K" → resolution = "4K"
        - "under 5000mah battery" → battery_mah <= 5000
        """
        constraints = []

        # ── Numeric attribute extraction ────────────────────────────
        numeric_patterns = [
            # "16gb ram" or "16gb"
            (r"(\d+)\s*gb\s*(?:ram)?", "ram_gb", "gte", "GB RAM"),
            # "512gb ssd" or "512gb storage"
            (r"(\d+)\s*gb\s*(?:ssd|storage|nvme)", "storage_gb", "gte", "GB storage"),
            # "50mp camera" or "50mp"
            (r"(\d+)\s*mp\s*(?:camera)?", "camera_mp", "gte", "MP camera"),
            # "5000mah battery"
            (r"(\d+)\s*mah", "battery_mah", "gte", "mAh battery"),
            # "40 hour battery" or "40 hours"
            (r"(\d+)\s*(?:hour|hr|hrs|hours?)\s*(?:battery|life)?", "battery_life_hours", "gte", "hour battery"),
            # "battery 40 hours"
            (r"battery\s*(?:life)?\s*(\d+)\s*(?:hour|hr|hrs|hours?)", "battery_life_hours", "gte", "hour battery"),
            # "55 inch" or "55 inch screen"
            (r"(\d+(?:\.\d+)?)\s*(?:inch|inches|\"|\")\s*(?:screen|display|tv)?", "screen_size_inches", "approx", "inch screen"),
            # "12000 dpi"
            (r"(\d+)\s*dpi", "dpi", "gte", "DPI"),
            # "120hz" or "120 hz"
            (r"(\d+)\s*hz", "refresh_rate_hz", "gte", "Hz refresh rate"),
            # "16gb ram 512gb" (ram already handled above)
            # "32gb" alone (without ram/storage context)
            (r"(?<!\w)(\d+)\s*gb(?!\s*(?:ram|ssd|storage))", "ram_gb", "gte", "GB RAM"),
            # "20000 rupees" — this is budget, not attribute
            # "8gb ram" patterns with context
        ]

        for pattern, attr_key, op, raw_text in numeric_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                value = float(match.group(1))
                # Avoid extracting prices as attributes
                if attr_key in ("ram_gb", "storage_gb") and value > 2048:
                    continue
                if attr_key == "screen_size_inches" and value > 100:
                    continue
                constraints.append(SearchConstraint(attr_key, value, op, raw_text))

        # ── Boolean attribute extraction ────────────────────────────
        for phrase, attr_key in BOOLEAN_ALIASES.items():
            # Match the phrase as a whole word/phrase
            pattern = r"(?:\b|(?<=\s))" + re.escape(phrase) + r"(?:\b|(?=\s))"
            if re.search(pattern, message, re.IGNORECASE):
                # Don't add duplicate constraints
                if not any(c.key == attr_key and c.operator == "eq" for c in constraints):
                    constraints.append(SearchConstraint(attr_key, True, "eq", phrase))

        # ── String attribute extraction ─────────────────────────────
        # Resolution patterns
        resolution_patterns = [
            (r"\b(4k)\b", "4K"),
            (r"\b(8k)\b", "8K"),
            (r"\b(fhd|full\s*hd|1080p)\b", "Full HD"),
            (r"\b(hd|720p)\b", "HD"),
            (r"\b(qhd|2k|1440p)\b", "2K"),
            (r"\b(uhd)\b", "4K UHD"),
        ]
        for pattern, value in resolution_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                if not any(c.key == "resolution" for c in constraints):
                    constraints.append(SearchConstraint("resolution", value, "eq", value))
                    break

        # Processor patterns
        processor_patterns = [
            (r"\b(core\s*i[3579])\b", "processor"),
            (r"\b(ryzen\s*\d)\b", "processor"),
            (r"\b(m[123])\b", "processor"),
            (r"\b(snapdragon\s*\d+\s*\w*)\b", "processor"),
            (r"\b(dimensity\s*\d+\w*)\b", "processor"),
            (r"\b(exynos\s*\d+\w*)\b", "processor"),
        ]
        for pattern, attr in processor_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                if not any(c.key == "processor" for c in constraints):
                    constraints.append(SearchConstraint("processor", match.group(1).strip(), "contains", match.group(1).strip()))

        # OS patterns
        os_patterns = [
            (r"\b(windows)\b", "Windows"),
            (r"\b(macos|mac\s*os)\b", "macOS"),
            (r"\b(android)\b", "Android"),
            (r"\b(ios|ipados)\b", "iOS"),
            (r"\b(chrome\s*os)\b", "Chrome OS"),
        ]
        for pattern, value in os_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                if not any(c.key == "operating_system" for c in constraints):
                    constraints.append(SearchConstraint("operating_system", value, "contains", value))

        # Switch type patterns (for keyboards)
        switch_patterns = [
            (r"\b(blue\s*switch)", "Blue"),
            (r"\b(brown\s*switch)", "Brown"),
            (r"\b(red\s*switch)", "Red"),
            (r"\b(mechanical)\b", "mechanical"),
            (r"\b(membrane)\b", "membrane"),
        ]
        for pattern, value in switch_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                if not any(c.key == "switch_type" for c in constraints):
                    constraints.append(SearchConstraint("switch_type", value, "eq", value))

        return constraints
