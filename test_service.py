import json

from services.catalog_service import find_products
from services.gemini_service import (
    AIResult,
    GeminiServiceError,
    get_ai_recommendations,
    validate_ai_result,
)

form = {
    "category": "headphones",
    "use": "daily commute on a train",
    "preferences": "long battery life",
    "priority": "value",
}

within, over = find_products("headphones", 30)

print("=== TEST 1: real Gemini call ===")
try:
    result = get_ai_recommendations(within, over, form)
    print(json.dumps(result, indent=2))
except GeminiServiceError as e:
    print("Service error:", e)

print("\n=== TEST 2: fake product ids must be removed ===")
fake = AIResult.model_validate(
    {
        "summary": "test",
        "best_value_id": "fake-999",
        "recommendations": [
            {"product_id": "fake-999", "explanation": "invented", "pros": [], "cons": []},
            {"product_id": "hp-001", "explanation": "real product", "pros": ["cheap"], "cons": []},
            {"product_id": "hp-004", "explanation": "over budget, should drop", "pros": [], "cons": []},
        ],
        "over_budget_notes": [{"product_id": "fake-999", "note": "invented"}],
    }
)
cleaned = validate_ai_result(
    fake,
    within_ids={p["id"] for p in within},
    over_ids={p["id"] for p in over},
)
print(json.dumps(cleaned, indent=2))