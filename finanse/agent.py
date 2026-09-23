"""AML Graph Copilot — AI-ассистент комплаенс-офицера и AML-аналитика.

Подключается к OpenAI API (или совместимому эндпоинту NVIDIA NIM) и оснащен
3 инструментами финансовой разведки на графе:
- get_node_info(gid) — профиль узла, роль, обороты, колено и evidence.
- find_common_recipients(gids) — поиск общих получателей и казначеев (консолидаторов).
- get_cluster_summary(cluster_id) — гипотеза и состав ячейки/сообщества Louvain.
"""
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import networkx as nx
import pandas as pd
import openai

# Автоматическое определение путей к данным
ROOT = Path(__file__).resolve().parent

def _resolve_path(filename: str) -> Path:
    candidates = [
        ROOT / filename,
        ROOT / "out" / filename,
        ROOT / "data" / filename,
        ROOT.parent / filename,
        ROOT.parent / "out" / filename,
        ROOT.parent / "data" / filename,
        Path(filename),
    ]
    for p in candidates:
        if p.exists():
            return p
    return ROOT / filename

# Загрузка аналитических срезов
_nodes_roles_path = _resolve_path("nodes_roles.csv")
_edges_path = _resolve_path("edges.parquet")
_clusters_path = _resolve_path("clusters.csv")

if _nodes_roles_path.exists():
    nodes_roles = pd.read_csv(_nodes_roles_path, dtype={"gid": str})
else:
    nodes_roles = pd.DataFrame(columns=["gid", "role", "role_score", "priority_score", "cluster_id", "evidence"])

if _clusters_path.exists():
    clusters = pd.read_csv(_clusters_path)
else:
    clusters = pd.DataFrame(columns=["cluster_id", "n_nodes", "n_seed", "sum_kzt_internal", "hypothesis", "internal_share"])

# Инициализация направленного графа переводов со строковыми GID (без потери точности int64)
G = nx.DiGraph()
if _edges_path.exists():
    edges = pd.read_parquet(_edges_path)
    # Используем прямой zip колонок во избежание приведения int64 к float в iterrows
    for src, dst, sum_kzt in zip(edges["src"].astype(str), edges["dst"].astype(str), edges["sum_kzt"]):
        G.add_edge(src, dst, weight=float(sum_kzt))

# --- ИНСТРУМЕНТЫ АГЕНТА ---

def get_node_info(gid: Union[int, str]) -> str:
    """Возвращает финансовый профиль узла по GID (роль, суммы, входящие и исходящие связи)."""
    gid_str = str(gid).strip()
    row = nodes_roles[nodes_roles["gid"] == gid_str]
    if row.empty:
        return json.dumps({"error": f"Клиент {gid_str} не найден в текущем графе."}, ensure_ascii=False)

    r = row.iloc[0]
    in_edges = list(G.in_edges(gid_str, data=True)) if gid_str in G else []
    out_edges = list(G.out_edges(gid_str, data=True)) if gid_str in G else []

    # Расчет сумм по графу либо из предрассчитанного снимка
    in_sum = sum(d.get("weight", 0.0) for _, _, d in in_edges)
    if in_sum == 0 and "in_kzt" in r and float(r["in_kzt"]) > 0:
        in_sum = float(r["in_kzt"])

    out_sum = sum(d.get("weight", 0.0) for _, _, d in out_edges)
    if out_sum == 0 and "out_kzt" in r and float(r["out_kzt"]) > 0:
        out_sum = float(r["out_kzt"])

    in_degree = len(in_edges) if in_edges else (int(r["in_deg"]) if "in_deg" in r else 0)
    out_degree = len(out_edges) if out_edges else (int(r["out_deg"]) if "out_deg" in r else 0)

    return json.dumps({
        "gid": str(gid_str),
        "role": str(r["role"]),
        "role_score": float(r["role_score"]),
        "priority_score": float(r["priority_score"]),
        "cluster_id": int(r["cluster_id"]),
        "in_degree": in_degree,
        "out_degree": out_degree,
        "in_volume_kzt": round(in_sum, 2),
        "out_volume_kzt": round(out_sum, 2),
        "evidence": str(r["evidence"]),
        "is_seed": bool(r.get("is_seed", False)) if "is_seed" in r else False,
        "depth": int(r["depth"]) if "depth" in r else None,
    }, ensure_ascii=False)


def find_common_recipients(gids: List[Union[int, str]]) -> str:
    """Находит, в какие общие узлы отправляли деньги указанные клиенты (поиск консолидатора/казначея)."""
    str_gids = [str(g).strip() for g in gids if str(g).strip()]

    if not str_gids:
        return json.dumps({"error": "Список GID пуст или содержит некорректные значения."}, ensure_ascii=False)

    recipients_per_node = [set(G.successors(g)) for g in str_gids if g in G]
    if not recipients_per_node:
        return json.dumps({
            "input_gids": str_gids,
            "common_recipients": [],
            "count": 0,
            "message": "Указанные клиенты не имеют исходящих связей в графе."
        }, ensure_ascii=False)

    common = set.intersection(*recipients_per_node)
    
    # Дополняем информацией о ролях общих получателей
    common_details = []
    for c_gid in sorted(common):
        row = nodes_roles[nodes_roles["gid"] == c_gid]
        role = str(row.iloc[0]["role"]) if not row.empty else "unknown"
        priority = float(row.iloc[0]["priority_score"]) if not row.empty else 0.0
        evidence = str(row.iloc[0]["evidence"]) if not row.empty else ""
        common_details.append({
            "gid": str(c_gid),
            "role": role,
            "priority_score": priority,
            "is_consolidator": (role == "consolidator"),
            "evidence": evidence
        })

    return json.dumps({
        "input_gids": str_gids,
        "common_recipients": sorted(list(common)),
        "common_details": common_details,
        "count": len(common),
    }, ensure_ascii=False)


def get_cluster_summary(cluster_id: int) -> str:
    """Выдает гипотезу, оборот и состав сообщества (ячейки) по номеру cluster_id."""
    try:
        c_id = int(cluster_id)
    except ValueError:
        return json.dumps({"error": f"Некорректный номер кластера: '{cluster_id}'"}, ensure_ascii=False)

    c_row = clusters[clusters["cluster_id"] == c_id]
    if c_row.empty:
        return json.dumps({"error": f"Сообщество (кластер) #{c_id} не найдено."}, ensure_ascii=False)

    r = c_row.iloc[0]
    members = nodes_roles[nodes_roles["cluster_id"] == c_id]
    role_dist = members["role"].value_counts().to_dict() if not members.empty else {}
    top_members = members.sort_values(by="priority_score", ascending=False).head(5)["gid"].tolist() if not members.empty else []

    return json.dumps({
        "cluster_id": c_id,
        "n_nodes": int(r["n_nodes"]),
        "n_seed": int(r["n_seed"]),
        "sum_kzt_internal": float(r["sum_kzt_internal"]),
        "hypothesis": str(r["hypothesis"]),
        "internal_share": float(r["internal_share"]),
        "top_sender_share": float(r["top_sender_share"]) if "top_sender_share" in r else None,
        "top_recipient_share": float(r["top_recipient_share"]) if "top_recipient_share" in r else None,
        "roles_distribution": role_dist,
        "top_priority_gids": [str(x) for x in top_members],
    }, ensure_ascii=False)


# --- СИСТЕМНЫЙ ПРОМПТ И СПЕЦИФИКАЦИЯ ИНСТРУМЕНТОВ ---

SYSTEM_PROMPT = """Ты — строгий AI-ассистент AML-аналитика банка второго уровня («AML Graph Copilot»).
Твоя задача — помогать расследовать сеть незаконного оборота средств по транзакционному графу (кейс «Граф денег»).
Правила:
1. Опирайся ТОЛЬКО на предоставленные факты из вызовов функций (суммы, роли, транзиты, сообщества).
2. Никогда не придумывай ФИО, пол, возраст или внешние данные — используй только числовые GID клиентов.
3. Формулируй выводы строго и профессионально, как гипотезы для проверки (например: "имеет признаки точки аккумуляции / казначея", "характерная роль транзитного узла").
4. При анализе сумм форматируй их с разделением тысяч и знаком валюты (например: 2 160 500,00 ₸).
5. Если найдены общие получатели, укажи их роль и поясни, аккумулируют ли они средства.
"""

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_node_info",
            "description": "Получить профиль узла по GID (роль, входящие и исходящие суммы, связи, evidence)",
            "parameters": {
                "type": "object",
                "properties": {
                    "gid": {"type": "string", "description": "Идентификатор клиента (GID)"}
                },
                "required": ["gid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_common_recipients",
            "description": "Найти общих получателей для списка GID (выявление казначея / консолидатора)",
            "parameters": {
                "type": "object",
                "properties": {
                    "gids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список GID клиентов",
                    }
                },
                "required": ["gids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cluster_summary",
            "description": "Получить аналитическую гипотезу, оборот и состав сообщества (кластера) по ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "cluster_id": {"type": "integer", "description": "Номер кластера (0-90)"}
                },
                "required": ["cluster_id"],
            },
        },
    },
]

DEFAULT_TOKEN = os.getenv("OPENAI_API_KEY", "")


# --- ЛОКАЛЬНЫЙ РЕЖИМ (FALLBACK) ---

def _format_money(amount: float) -> str:
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",") + " ₸"


def _local_reasoning_fallback(query: str) -> Dict[str, Any]:
    """Интеллектуальный локальный агент на случай недоступности внешнего LLM API."""
    tools_called = []
    
    # 1. Поиск GID в запросе (18-значные числа или последовательности от 5 цифр)
    gids = re.findall(r"\b1\d{17}\b", query)
    if not gids:
        gids = re.findall(r"\b\d{6,19}\b", query)

    # 2. Поиск номера кластера/сообщества
    cluster_match = re.search(r"(?:кластер[а-я]*|сообществ[а-я]*|групп[а-я]*|ячейк[а-я]*)\s*(?:#|№)?\s*(\d{1,3})", query, re.IGNORECASE)

    lower_query = query.lower()

    # Сценарий 1: Сводка по кластеру / сообществу
    if cluster_match:
        c_id = int(cluster_match.group(1))
        raw_res = get_cluster_summary(c_id)
        data = json.loads(raw_res)
        tools_called.append({"tool": "get_cluster_summary", "args": {"cluster_id": c_id}, "result": data})

        if "error" in data:
            return {"answer": data["error"], "tools_called": tools_called, "engine": "local_aml_rules"}

        hyp = data.get("hypothesis", "")
        n_nodes = data.get("n_nodes", 0)
        n_seed = data.get("n_seed", 0)
        sum_kzt = _format_money(data.get("sum_kzt_internal", 0.0))
        top_gids = data.get("top_priority_gids", [])

        answer = (
            f"**Аналитическая сводка по сообществу (кластеру #{c_id}):**\n\n"
            f"- **Гипотеза структуры:** {hyp}\n"
            f"- **Масштаб:** {n_nodes} участников, из них {n_seed} исходных seed-закладчиков.\n"
            f"- **Внутренний оборот сообщества:** {sum_kzt}\n"
            f"- **Ключевые узлы кластера по приоритету проверки:**\n"
        )
        for tg in top_gids:
            answer += f"  • GID `{tg}`\n"
        answer += "\n*Рекомендация:* Проверить топовые узлы на предмет координирования финансовых потоков внутри ячейки."
        return {"answer": answer, "tools_called": tools_called, "engine": "local_aml_rules"}

    # Сценарий 2: Поиск общих получателей / казначея (по нескольким GID или ключевым словам)
    has_common_intent = bool(re.search(r"\b(?:общ[а-я]*|аккумулир[а-я]*|казначе[а-я]*|стека[а-я]*)\b", lower_query))
    if len(gids) >= 2 or has_common_intent:
        target_gids = gids if gids else ["100000000331309100", "100000007629096100"]
        raw_res = find_common_recipients(target_gids)
        data = json.loads(raw_res)
        tools_called.append({"tool": "find_common_recipients", "args": {"gids": target_gids}, "result": data})

        count = data.get("count", 0)
        common_nodes = data.get("common_recipients", [])
        details = data.get("common_details", [])

        if count == 0:
            answer = (
                f"**Результат расследования связей:**\n\n"
                f"Для клиентов `{', '.join(target_gids)}` **не обнаружено прямых общих получателей** первого колена.\n"
                f"Денежные потоки от данных участников направляются разным контрагентам либо расходятся по независимым транзитным ветвям."
            )
        else:
            answer = (
                f"**Обнаружены точки пересечения денежных потоков:**\n\n"
                f"Клиенты `{', '.join(target_gids)}` имеют **{count} общих получателей**:\n\n"
            )
            for item in details:
                c_gid = item["gid"]
                role = item["role"]
                p_score = item["priority_score"]
                role_badge = "🔥 **Казначей (Consolidator)**" if item["is_consolidator"] else f"Узел роли `{role}`"
                answer += f"- **GID `{c_gid}`** — {role_badge} (приоритет: `{p_score:.4f}`).\n"
                if item.get("evidence"):
                    answer += f"  *Обоснование:* {item['evidence']}\n"
            answer += (
                f"\n**Заключение комплаенс-офицера:** Выявленный узел аккумулирует средства от нескольких источников "
                f"и имеет высокую вероятность участия в централизованном сборе теневой выручки."
            )
        return {"answer": answer, "tools_called": tools_called, "engine": "local_aml_rules"}

    # Сценарий 3: Профиль узла по GID
    if gids:
        gid = gids[0]
        raw_res = get_node_info(gid)
        data = json.loads(raw_res)
        tools_called.append({"tool": "get_node_info", "args": {"gid": gid}, "result": data})

        if "error" in data:
            return {"answer": data["error"], "tools_called": tools_called, "engine": "local_aml_rules"}

        role = data.get("role", "неизвестно")
        p_score = data.get("priority_score", 0.0)
        r_score = data.get("role_score", 0.0)
        in_vol = _format_money(data.get("in_volume_kzt", 0.0))
        out_vol = _format_money(data.get("out_volume_kzt", 0.0))
        in_deg = data.get("in_degree", 0)
        out_deg = data.get("out_degree", 0)
        c_id = data.get("cluster_id", 0)
        evidence = data.get("evidence", "")

        answer = (
            f"**Досье участника транзакционного графа (GID: `{gid}`):**\n\n"
            f"- **Структурная роль:** `{role}` (сила правила: `{r_score:.2f}`, приоритет проверки: `{p_score:.4f}`)\n"
            f"- **Принадлежность к сообществу:** Кластер #{c_id}\n"
            f"- **Входящий финансовый поток:** {in_vol} (контрагентов: {in_deg})\n"
            f"- **Исходящий финансовый поток:** {out_vol} (контрагентов: {out_deg})\n"
            f"- **Числовое обоснование:** {evidence}\n\n"
            f"**Оценка риска:** Узел требует повышенного внимания службы комплаенс. "
            f"Рекомендуется запросить детализацию назначения платежей и остатки по счетам."
        )
        return {"answer": answer, "tools_called": tools_called, "engine": "local_aml_rules"}

    # Сценарий 4: Общий вопрос / справка
    return {
        "answer": (
            "Здравствуйте! Я — **AML Graph Copilot**, интеллектуальный ассистент по расследованию транзакционного графа.\n\n"
            "Вы можете задавать мне вопросы на естественном языке, например:\n"
            "- *«Каков финансовый профиль узла 100000003115284100?»*\n"
            "- *«Кто аккумулирует средства с клиентов 100000000331309100 и 100000007629096100?»*\n"
            "- *«Дай сводку по сообществу 11»*\n"
            "- *«Найди общих получателей для 100000004156082100 и 100000008547844100»*"
        ),
        "tools_called": [],
        "engine": "local_aml_rules"
    }


# --- ГЛАВНАЯ ФУНКЦИЯ ВЫЗОВА АГЕНТА ---

def ask_aml_agent(
    query: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: str = "gpt-4o-mini"
) -> str:
    """Выполняет запрос к AI-агенту.

    При наличии валидного ключа OpenAI или NVIDIA NIM выполняет Tool-calling.
    В случае ошибки аутентификации, таймаута или отсутствия сети плавно переключается
    на детерминированный локальный движок правил с вызовом тех же инструментов.
    """
    key = api_key or os.getenv("OPENAI_API_KEY") or DEFAULT_TOKEN
    if not key:
        return _local_reasoning_fallback(query)["answer"]
    b_url = base_url or os.getenv("OPENAI_BASE_URL")

    # Попытка вызова внешнего LLM API
    try:
        client = openai.OpenAI(api_key=key, base_url=b_url)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=AGENT_TOOLS,
            tool_choice="auto",
            timeout=3.0
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            messages.append(response_message)
            for tool_call in tool_calls:
                fn_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                if fn_name == "get_node_info":
                    res = get_node_info(args.get("gid", ""))
                elif fn_name == "find_common_recipients":
                    res = find_common_recipients(args.get("gids", []))
                elif fn_name == "get_cluster_summary":
                    res = get_cluster_summary(args.get("cluster_id", 0))
                else:
                    res = json.dumps({"error": f"Функция {fn_name} не поддерживается"})

                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": fn_name,
                    "content": res,
                })

            final_response = client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=5.0
            )
            return final_response.choices[0].message.content or "Ответ сформирован."

        return response_message.content or "Ответ сформирован."

    except Exception:
        # Локальный fallback с гарантированной точностью по графу
        result = _local_reasoning_fallback(query)
        return result["answer"]


if __name__ == "__main__":
    print("=== AML Graph Copilot Console Test ===")
    test_q = "Кто аккумулирует средства с клиентов 100000000331309100 и 100000007629096100?"
    print(f"Вопрос: {test_q}\n")
    ans = ask_aml_agent(test_q)
    print(ans)
