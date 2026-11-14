import argparse
import asyncio
import csv
import json
import logging
import math
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = SERVICE_DIR.parent.parent
sys.path.insert(0, str(SERVICE_DIR))

QUESTION_COLS = ["question", "query", "msg", "message", "вопрос", "text", "user_message"]
REFERENCE_COLS = ["answer", "reference", "expected", "response", "ответ", "output", "ideal_answer"]
ID_COLS = ["id", "question_id", "qid", "№", "n"]
DIALOG_COLS = ["dialog_id", "dialogue_id", "session_id", "conversation_id", "chat_id", "диалог"]
LEAD_RE = re.compile(r"\[+\s*READY_FOR_LEAD\s*\]+", re.IGNORECASE)
NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
log = logging.getLogger("benchmark")
DIGIT_RE = re.compile(r"[1-5]")

JUDGE_SYSTEM = """Ты - строгий эксперт.
Сравни два ответа ИИ-консультанта МТС Energytool.
Ориентируйся на эталонный ответ: точность фактов, полнота, отсутствие выдумок,
уместные уточняющие вопросы, корректный отказ, если информации нет,
понятный язык и объём до 150 слов.
Выведи только одну цифру:
1 - ответ A значительно лучше
2 - ответ A немного лучше
3 - ответы сопоставимы
4 - ответ B немного лучше
5 - ответ B значительно лучше"""

JUDGE_USER = """Вопрос клиента:
{question}

Эталонный ответ:
{golden}

Ответ A:
{a}

Ответ B:
{b}

Какой ответ лучше? Одна цифра от 1 до 5:"""


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=None)
    p.add_argument("--questions", type=Path, default=None)
    p.add_argument("--reference", type=Path, default=None)
    p.add_argument("--out-dir", type=Path, default=PROJECT_DIR / ".data" / "benchmark")
    p.add_argument("--tag", default="")
    p.add_argument("--prompt", default="ConsultantPrompt")
    p.add_argument("--temperature", type=float, default=None)
    p.add_argument("--top-k", type=int, default=None)
    p.add_argument("--top-n", type=int, default=None)
    p.add_argument("--no-rerank", action="store_true")
    p.add_argument("--no-expand", action="store_true")
    p.add_argument("--with-summary", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--judge", action="store_true")
    p.add_argument("--baseline", type=Path, default=None)
    return p.parse_args()


def apply_env_overrides(args):
    if args.temperature is not None:
        os.environ["LLM_TEMPERATURE"] = str(args.temperature)
    if args.top_k is not None:
        os.environ["RAG_TOP_K"] = str(args.top_k)
    if args.top_n is not None:
        os.environ["RRK_TOP_N"] = str(args.top_n)
    if args.data_dir is not None:
        os.environ["DATA_DIR"] = str(args.data_dir)


def find_file(data_dir: Path, explicit: Path | None, patterns: list[str]) -> Path | None:
    if explicit:
        return explicit
    for pattern in patterns:
        found = sorted(data_dir.rglob(pattern))
        if found:
            return found[0]
    return None


def read_csv(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(text.splitlines(), dialect=dialect))
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in rows]


def pick_col(row: dict, names: list[str]) -> str | None:
    for name in names:
        if name in row:
            return name
    return None


def load_items(q_path: Path, r_path: Path | None) -> list[dict]:
    q_rows = read_csv(q_path)
    if not q_rows:
        raise SystemExit(f"Пустой файл: {q_path}")
    q_col = pick_col(q_rows[0], QUESTION_COLS)
    if not q_col:
        raise SystemExit(f"Не нашла колонку с вопросом. Колонки: {list(q_rows[0])}")
    id_col = pick_col(q_rows[0], ID_COLS)
    dlg_col = pick_col(q_rows[0], DIALOG_COLS)
    ref_col_in_q = pick_col(q_rows[0], REFERENCE_COLS)
    print(f"questions: {q_path} | вопрос={q_col} id={id_col} диалог={dlg_col}")

    refs_by_id, refs_by_pos = {}, []
    if r_path:
        r_rows = read_csv(r_path)
        r_col = pick_col(r_rows[0], REFERENCE_COLS) if r_rows else None
        r_id = pick_col(r_rows[0], ID_COLS) if r_rows else None
        if not r_col:
            cols = list(r_rows[0]) if r_rows else []
            raise SystemExit(f"Не нашла колонку с эталоном. Колонки: {cols}")
        print(f"reference: {r_path} | эталон={r_col} id={r_id}")
        for row in r_rows:
            refs_by_pos.append(row[r_col])
            if r_id:
                refs_by_id[row[r_id]] = row[r_col]

    items = []
    for i, row in enumerate(q_rows):
        qid = row[id_col] if id_col else str(i + 1)
        if ref_col_in_q and ref_col_in_q != q_col:
            ref = row[ref_col_in_q]
        elif qid in refs_by_id:
            ref = refs_by_id[qid]
        elif i < len(refs_by_pos):
            ref = refs_by_pos[i]
        else:
            ref = ""
        items.append(
            {
                "id": qid,
                "dialog": row[dlg_col] if dlg_col else qid,
                "question": row[q_col],
                "reference": ref,
            }
        )
    return items


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def numbers_recall(answer: str, reference: str) -> float | None:
    ref_nums = {n.replace(",", ".") for n in NUM_RE.findall(reference)}
    if not ref_nums:
        return None
    ans_nums = {n.replace(",", ".") for n in NUM_RE.findall(answer)}
    return len(ref_nums & ans_nums) / len(ref_nums)


async def judge_round(generate, question, golden, a, b):
    raw = await generate(
        prompt=JUDGE_USER.format(question=question, golden=golden, a=a, b=b),
        system_prompt=JUDGE_SYSTEM,
        temperature=0.0,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    found = DIGIT_RE.search(raw)
    return int(found.group()) if found else None


async def judge_item(generate, question, golden, baseline, answer):
    d1 = await judge_round(generate, question, golden, baseline, answer)
    d2 = await judge_round(generate, question, golden, answer, baseline)
    if d1 is None or d2 is None:
        return None
    return ((d1 - 1) / 4 + (5 - d2) / 4) / 2


def judge_metrics(scores):
    valid = [s for s in scores if s is not None]
    if not valid:
        return {}
    wins = sum(1 for s in valid if s > 0.5)
    losses = sum(1 for s in valid if s < 0.5)
    match_rate = sum(valid) / len(valid)
    win_rate = wins / (wins + losses) if wins + losses else 0.5
    return {
        "judged": len(valid),
        "match_rate": round(match_rate, 4),
        "win_rate": round(win_rate, 4),
        "score": round(0.7 * match_rate + 0.3 * win_rate, 4),
    }


async def run(args):
    from src.config import DATA_DIR, settings
    from src.core.embeddings import embed_texts
    from src.core.llm import generate_response
    from src.rag import pipeline, prompts
    from src.rag import retriever as retriever_module
    from src.schemas.domain.state import Message
    from src.summarization.pipeline import run_summarizer_pipeline

    prompt_cls = getattr(prompts, args.prompt, None)
    if prompt_cls is None:
        names = [n for n in dir(prompts) if n.startswith("Consultant")]
        raise SystemExit(f"Нет промпта {args.prompt}. Есть: {names}")
    pipeline.ConsultantPrompt = prompt_cls

    async def patched_retrieve(query, **kwargs):
        return await retriever_module.retrieve(
            query,
            with_rerank=not args.no_rerank and not settings.is_reranker_mock,
            with_expansion=not args.no_expand,
        )

    pipeline.retrieve = patched_retrieve

    data_dir = Path(args.data_dir or DATA_DIR)
    q_path = find_file(data_dir, args.questions, ["demo_questions*.csv", "*questions*.csv"])
    r_path = find_file(data_dir, args.reference, ["demo_output*.csv", "*output*.csv"])
    if not q_path or not q_path.exists():
        raise SystemExit(f"Не нашла файл с вопросами в {data_dir}. Укажи --questions путь")
    items = load_items(q_path, r_path)
    if args.limit:
        items = items[: args.limit]

    config = {
        "tag": args.tag,
        "prompt": args.prompt,
        "llm_model": settings.llm.model or "mock",
        "temperature": settings.llm.temperature,
        "top_k": settings.rag.top_k,
        "top_n": settings.reranker.top_n,
        "rerank": not args.no_rerank and not settings.is_reranker_mock,
        "expand": not args.no_expand,
        "with_summary": args.with_summary,
        "emb_mock": settings.is_embedding_mock,
    }
    print("config:", json.dumps(config, ensure_ascii=False))

    histories: dict[str, list] = {}
    summaries: dict[str, str | None] = {}
    results = []
    for n, item in enumerate(items, 1):
        history = histories.setdefault(item["dialog"], [])
        summary = summaries.get(item["dialog"])
        started = time.perf_counter()
        error = ""
        try:
            reply = await pipeline.run_rag_pipeline(
                Message(role="user", content=item["question"]), list(history), summary
            )
            answer, lead = reply.answer, reply.ready_for_lead
            sources = sorted({c.chunk.filepath for c in reply.chunks})
        except Exception as e:
            log.exception("pipeline упал на id=%s", item["id"])
            answer, lead, sources, error = "", False, [], f"{type(e).__name__}: {e}"
        elapsed = time.perf_counter() - started

        if answer:
            history.append(Message(role="user", content=item["question"]))
            history.append(Message(role="assistant", content=answer))
            if args.with_summary and (lead or summary):
                try:
                    summaries[item["dialog"]] = await run_summarizer_pipeline(
                        item["question"], answer, summary
                    )
                except Exception as e:
                    log.exception("summarizer упал на id=%s", item["id"])
                    error += f" summary: {type(e).__name__}: {e}"

        results.append(
            {
                "id": item["id"],
                "dialog": item["dialog"],
                "question": item["question"],
                "answer": answer,
                "reference": item["reference"],
                "ready_for_lead": lead,
                "words": len(answer.split()),
                "over_150": len(answer.split()) > 150,
                "marker_leak": bool(LEAD_RE.search(answer)),
                "numbers_recall": numbers_recall(answer, item["reference"]),
                "seconds": round(elapsed, 2),
                "sources": "; ".join(sources),
                "summary": summaries.get(item["dialog"]) or "",
                "error": error.strip(),
            }
        )
        print(f"{n:2d}/{len(items)} id={item['id']} {elapsed:.1f}s {answer[:70]!r} {error}")

    pairs = [(i, r) for i, r in enumerate(results) if r["answer"] and r["reference"]]
    if pairs and not settings.is_embedding_mock:
        texts = []
        for _, r in pairs:
            texts += [r["answer"], r["reference"]]
        vectors = await embed_texts(texts)
        for j, (i, _) in enumerate(pairs):
            results[i]["similarity"] = round(cosine(vectors[2 * j], vectors[2 * j + 1]), 4)

    baseline_answers = {}
    if args.baseline:
        b_rows = read_csv(args.baseline)
        b_col = pick_col(b_rows[0], REFERENCE_COLS)
        b_id = pick_col(b_rows[0], ID_COLS)
        baseline_answers = {row[b_id]: row[b_col] for row in b_rows} if b_id and b_col else {}

    if args.judge:
        for r in results:
            if not r["answer"] or not r["reference"]:
                continue
            opponent = baseline_answers.get(r["id"], r["reference"])
            try:
                r["judge"] = await judge_item(
                    generate_response, r["question"], r["reference"], opponent, r["answer"]
                )
            except Exception:
                log.exception("судья упал на id=%s", r["id"])
            print(f"judge id={r['id']} {r.get('judge')}")

    def mean(key):
        vals = [r[key] for r in results if isinstance(r.get(key), int | float)]
        return round(sum(vals) / len(vals), 4) if vals else None

    total = len(results)
    metrics = {
        "n": total,
        "errors": sum(1 for r in results if r["error"]),
        "similarity": mean("similarity"),
        "numbers_recall": mean("numbers_recall"),
        "over_150_share": round(sum(r["over_150"] for r in results) / total, 4),
        "marker_leak_share": round(sum(r["marker_leak"] for r in results) / total, 4),
        "lead_share": round(sum(r["ready_for_lead"] for r in results) / total, 4),
        "avg_seconds": mean("seconds"),
        **judge_metrics([r.get("judge") for r in results]),
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"{stamp}_{args.tag}" if args.tag else stamp
    out_csv = args.out_dir / f"{name}.csv"
    fields = list(results[0].keys() | {"similarity", "judge"})
    order = ["id", "dialog", "question", "answer", "reference", "judge", "similarity"]
    fields = order + [f for f in fields if f not in order]
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    summary_path = args.out_dir / "summary.jsonl"
    with summary_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"run": name, **config, **metrics}, ensure_ascii=False) + "\n")

    print()
    for key, value in metrics.items():
        print(f"{key:18s} {value}")
    print(f"\nОтветы: {out_csv}\nИтоги всех прогонов: {summary_path}")


def main():
    args = parse_args()
    apply_env_overrides(args)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()