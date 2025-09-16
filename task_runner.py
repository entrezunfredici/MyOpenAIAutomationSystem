from openai import OpenAI
import json, pathlib, datetime as dt

client = OpenAI()

def run_task(task):
    prompt = f"""Tu es un agent nocturne. Tâche: {task['goal']}
Contrainte: réponds en JSON {{ "status": "...", "summary": "..." }}."""
    resp = client.responses.create(
        model="gpt-5",  # ou celui que tu utilises côté API
        input=[{"role":"user","content":prompt}],
        max_output_tokens=1200
    )
    text = resp.output_text
    return json.loads(text)

def main():
    tasks = json.loads(pathlib.Path("/opt/nightbot/tasks.json").read_text())
    out_dir = pathlib.Path("/opt/nightbot/out"); out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for t in tasks:
        try:
            r = run_task(t); r["task_id"]=t["id"]; r["ts"]=dt.datetime.utcnow().isoformat()
            results.append(r)
        except Exception as e:
            results.append({"task_id":t["id"], "status":"error", "error":str(e)})
    pathlib.Path(out_dir/"last_run.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
