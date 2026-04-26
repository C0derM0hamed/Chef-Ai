import json

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
system_prompt = """
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


@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def chef_assistant(request):
    if request.method == "GET":
        return render(request, "kitchen/index.html")

    ingredients = (request.POST.get("ingredients") or "").strip()
    if not ingredients:
        return JsonResponse(
            {"error": "Please enter at least one ingredient.", "meals": []},
            status=400,
        )

    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": (
                    system_prompt
                    + " Use these ingredients: "
                    + ingredients
                ),
            }
        ],
    )

    try:
        full_response = ""
        for chunk in llm.stream([message]):
            if chunk.content:
                full_response += chunk.content

        clean = full_response.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean)
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
            "servings": m.get("servings", 0),
            "ingredients": m.get("ingredients", []),
            "instructions": m.get("instructions", []),
        }
        for m in data
    ]
    return JsonResponse({"error": None, "meals": meals})
