import base64
import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from .nutrition_tools import save_nutrition_to_csv, search_nutrition_places

load_dotenv()
llm = init_chat_model(
    "gpt-4o-mini",
    temperature=0.7,
)

DISCLAIMER = settings.MEDICAL_DISCLAIMER

system_prompt = """
You are a Nutrition AI Agent. You help users think about food and estimated
nutrition; you are not a doctor or registered dietitian.

You can use tools:
- search_nutrition_places: when the user asks to find healthy restaurants,
  grocery stores, "near me" options, or broad nutrition background for a topic.
- save_nutrition_to_csv: after you have analyzed a specific meal with numbers
  and short text, to log that row (user may want a record).

Behavior:
- If the user mainly wants places or general info, call search first, then answer
  clearly; a short helpful message is fine if there is no meal to score.
- If the user describes or shows a meal (text and/or image), estimate nutrition
  and call save when you have solid numbers. Extract food clearly from images;
  combine image and text when both exist.
- Final meal analysis must be JSON only: a single array, no markdown.

Meal JSON shape (array of one or more objects):
[
  {
    "meal": "",
    "calories": 0,
    "protein": 0,
    "carbs": 0,
    "fats": 0,
    "ingredients": [],
    "summary": "",
    "recommendations": []
  }
]

Use numbers for macros and calories (rough estimates). ingredients is a list of
strings. recommendations is a list of short strings.
"""


def _tc_id(tc):
    if isinstance(tc, dict):
        return tc.get("id") or ""
    return getattr(tc, "id", "") or ""


def _tc_name(tc):
    if isinstance(tc, dict):
        return tc.get("name") or ""
    return getattr(tc, "name", "") or ""


def _tc_args(tc):
    if isinstance(tc, dict):
        args = tc.get("args")
    else:
        args = getattr(tc, "args", None)
    if args is None and isinstance(tc, dict):
        args = tc.get("function", {}).get("arguments")
    if isinstance(args, str):
        return json.loads(args) if args.strip() else {}
    return args or {}


def _build_user_human_message(user_text, image_url):
    if image_url:
        if user_text:
            t = (
                user_text
                + "\n\nUse the photo: identify foods, estimate portions if you can, "
                "and combine with the text above."
            )
        else:
            t = (
                "The user sent only a photo. Identify foods in the image and "
                "estimate nutrition for the meal you infer."
            )
        return HumanMessage(
            content=[
                {"type": "text", "text": t},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        )
    return HumanMessage(content=user_text)


def _summarize_old_turn(prior, dropped):
    content = dropped.get("content", "") if isinstance(dropped, dict) else str(dropped)
    prompt = (
        "Merge into at most 3 short English sentences of running user context. "
        "Do not give medical advice; only summarize what was discussed.\n\n"
        f"Prior memory:\n{prior}\n\nOldest message to fold in:\n{content}"
    )
    r = llm.invoke([HumanMessage(content=prompt)])
    return (r.content or "").strip()


def _update_session_history(request, user_text, assistant_text):
    hist = request.session.get("nutr_history", [])
    hist.append({"role": "user", "content": user_text})
    hist.append({"role": "assistant", "content": (assistant_text or "")[:12000]})
    while len(hist) > 5:
        dropped = hist.pop(0)
        request.session["nutr_summary"] = _summarize_old_turn(
            request.session.get("nutr_summary", ""),
            dropped,
        )
    request.session["nutr_history"] = hist
    request.session.modified = True


def _run_nutrition_agent(request, user_text, image_url):
    tools = [search_nutrition_places, save_nutrition_to_csv]
    by_name = {t.name: t for t in tools}
    llm_tools = llm.bind_tools(tools)

    sys_parts = [
        system_prompt,
        "",
        "Required disclosure for your reasoning and summaries:",
        DISCLAIMER,
    ]
    if request.session.get("nutr_summary"):
        sys_parts.extend(
            [
                "",
                "Longer-term summarized context from earlier turns:",
                request.session["nutr_summary"],
            ],
        )
    messages = [SystemMessage(content="\n".join(sys_parts))]
    for turn in request.session.get("nutr_history", []):
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        else:
            messages.append(AIMessage(content=turn["content"]))
    messages.append(_build_user_human_message(user_text, image_url))

    search_results = None
    final_content = None

    for _ in range(8):
        ai = llm_tools.invoke(messages)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            final_content = ai.content or ""
            break
        messages.append(ai)
        for tc in tool_calls:
            name = _tc_name(tc)
            args = _tc_args(tc)
            tid = _tc_id(tc)
            tool_fn = by_name.get(name)
            if tool_fn is None:
                out = f"Unknown tool: {name}"
            else:
                out = tool_fn.invoke(args)
                if name == "search_nutrition_places":
                    try:
                        search_results = json.loads(out)
                    except (json.JSONDecodeError, TypeError):
                        search_results = {"raw": out}
            messages.append(ToolMessage(content=str(out), tool_call_id=tid))
    else:
        return (
            None,
            "The agent used too many tool steps. Try a simpler question.",
            None,
        )

    if final_content is None:
        return None, "No final response from the model.", search_results
    return final_content, None, search_results


def _normalize_meal(m):
    return {
        "meal": m.get("meal", ""),
        "calories": m.get("calories", 0),
        "protein": m.get("protein", 0),
        "carbs": m.get("carbs", 0),
        "fats": m.get("fats", 0),
        "ingredients": m.get("ingredients", []),
        "summary": m.get("summary", ""),
        "recommendations": m.get("recommendations", []),
    }


@ensure_csrf_cookie
@require_http_methods(["GET", "POST"])
def chef_assistant(request):
    if request.method == "GET":
        return render(
            request,
            "kitchen/index.html",
            {"disclaimer": DISCLAIMER},
        )

    user_text = (request.POST.get("ingredients") or "").strip()
    photo = request.FILES.get("photo")

    if not user_text and not photo:
        return JsonResponse(
            {
                "error": "Add a message in the text box and/or upload a photo.",
                "meals": [],
                "search_results": None,
                "assistant_message": None,
                "disclaimer": DISCLAIMER,
            },
            status=400,
        )

    if photo:
        mime = (getattr(photo, "content_type", None) or "image/png").split(";")[
            0
        ].strip()
        if not mime.startswith("image/"):
            return JsonResponse(
                {
                    "error": "Please choose an image file (PNG, JPEG, …).",
                    "meals": [],
                    "search_results": None,
                    "assistant_message": None,
                    "disclaimer": DISCLAIMER,
                },
                status=400,
            )
        b64 = base64.b64encode(photo.read()).decode("ascii")
        image_url = f"data:{mime};base64,{b64}"
    else:
        image_url = None

    try:
        raw_text, agent_err, search_results = _run_nutrition_agent(
            request,
            user_text,
            image_url,
        )
    except Exception as e:
        return JsonResponse(
            {
                "error": str(e),
                "meals": [],
                "search_results": None,
                "assistant_message": None,
                "disclaimer": DISCLAIMER,
            },
            status=502,
        )

    if agent_err:
        return JsonResponse(
            {
                "error": agent_err,
                "meals": [],
                "search_results": search_results,
                "assistant_message": None,
                "disclaimer": DISCLAIMER,
            },
            status=502,
        )

    clean = (raw_text or "").replace("```json", "").replace("```", "").strip()
    meals = []
    assistant_message = None
    try:
        data = json.loads(clean)
        if isinstance(data, list):
            meals = [_normalize_meal(x) for x in data]
        else:
            assistant_message = raw_text
    except (json.JSONDecodeError, TypeError):
        assistant_message = raw_text

    if not meals and not assistant_message:
        assistant_message = raw_text

    _update_session_history(
        request,
        user_text or "(photo only)",
        raw_text or "",
    )

    return JsonResponse(
        {
            "error": None,
            "meals": meals,
            "search_results": search_results,
            "assistant_message": assistant_message,
            "disclaimer": DISCLAIMER,
        },
    )
