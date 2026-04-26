import json
import re

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

# Same setup as ai_chef.ipynb: load env, then model.
load_dotenv()
llm = init_chat_model(
    "gpt-4o-mini",
    temperature=0.7,
)

# Same system prompt as the notebook (JSON array of meals).
SYSTEM_PROMPT = """
You are a chef.

Give meals based on ingredients.
Return JSON only. No markdown.

Format:
[
  {
    "name": "",
    "cooking_time": 0,
    "servings": 0,
    "ingredients": [
      {"name": "", "status": "available or missing"}
    ],
    "instructions": []
  }
]
"""


def _stream_llm_to_text(message: HumanMessage) -> str:
    """Accumulate streamed tokens — same pattern as the notebook (cells 7–8)."""
    full_response = ""
    for chunk in llm.stream([message]):
        if chunk.content:
            full_response += chunk.content
    return full_response


def _parse_model_json(raw: str) -> list:
    """json.loads on model output; strip optional markdown fences if the model adds them."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\s*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return json.loads(text)


@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def chef_assistant(request):
    """
    Single view: GET — page with form; POST — JSON meals (name, cooking_time, instructions only).
    AI path matches the notebook, but ingredients come from the form text (not an image).
    """
    if request.method == "GET":
        return render(request, "kitchen/index.html")

    # POST: ingredients from form
    ingredients = (request.POST.get("ingredients") or "").strip()
    if not ingredients:
        return JsonResponse(
            {"error": "Please enter at least one ingredient.", "meals": []},
            status=400,
        )

    # Text-only HumanMessage (notebook used text + image; we keep the same list-of-parts shape).
    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": (
                    SYSTEM_PROMPT
                    + " Use these ingredients: "
                    + ingredients
                ),
            }
        ],
    )

    try:
        full_response = _stream_llm_to_text(message)
        data = _parse_model_json(full_response)
    except (json.JSONDecodeError, TypeError) as e:
        return JsonResponse(
            {
                "error": f"Could not parse the model response as JSON: {e}",
                "meals": [],
            },
            status=502,
        )
    except Exception as e:
        return JsonResponse(
            {"error": str(e), "meals": []},
            status=502,
        )

    meals = [
        {
            "name": m.get("name", ""),
            "cooking_time": m.get("cooking_time", 0),
            "instructions": m.get("instructions", []),
        }
        for m in data
    ]
    return JsonResponse({"error": None, "meals": meals})
