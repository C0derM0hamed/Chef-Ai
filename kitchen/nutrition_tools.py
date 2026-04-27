"""Simple tools for the Nutrition AI agent (mock search + CSV log)."""
import csv
import json
from pathlib import Path

from django.conf import settings
from langchain_core.tools import tool


@tool
def search_nutrition_places(query: str) -> str:
    """
    Use when the user wants healthy restaurants, grocery stores, or general
    nutrition information for a location or search topic. Examples: "healthy
    food near me", "where to buy organic vegetables", "low-sodium takeout ideas".
    """
    result = {
        "restaurants": [
            {
                "name": "Green Bowl Café (mock)",
                "note": "Salads, grain bowls, and grilled protein — sample data.",
            },
            {
                "name": "Mediterranean Fresh (mock)",
                "note": "Grilled fish, legumes, vegetables — sample data.",
            },
        ],
        "grocery_stores": [
            {
                "name": "Local Fresh Market (mock)",
                "note": "Produce, bulk whole grains, lean proteins — sample data.",
            },
            {
                "name": "Neighborhood Co-op (mock)",
                "note": "Organic options and local produce — sample data.",
            },
        ],
        "nutrition_info": [
            "A balanced meal often includes vegetables, a lean protein, and whole "
            "grains; portions depend on your needs — this is general information only.",
            f'Search context: {query!r} — these listings are mock data, not live API results.',
        ],
    }
    return json.dumps(result, ensure_ascii=False)


@tool
def save_nutrition_to_csv(
    meal: str,
    calories: int,
    summary: str,
    recommendations: str,
) -> str:
    """
    Save one analyzed meal row to a local CSV file. Use after you have
    reasonable estimates and the user is describing a concrete meal to record.
    Pass recommendations as a single string; use " | " between items if several.
    """
    path: Path = settings.NUTRITION_CSV_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(
                ["meal", "calories", "summary", "recommendations"],
            )
        writer.writerow([meal, calories, summary, recommendations])
    return f"Saved to {path.name}."
