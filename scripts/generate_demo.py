"""Deterministic fictional fixtures, never a Live fallback."""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.models import Edition  # noqa: E402

rows = [
    ("나루시, 심야 버스 노선 두 곳 시범 운영", "늦은 밤 이동을 돕는 새 노선을 한 달 동안 시험합니다.",
     "나루시는 밤늦게 귀가하는 주민을 위한 이동 수단을 검토해 왔습니다.",
     "나루시는 심야 버스 두 노선을 한 달간 시범 운영한다고 발표했습니다. 운행 결과를 살펴본 뒤 정식 운영 여부를 결정할 예정입니다.",
     "나루시 교통과는 이용자 의견을 받아 노선과 시간을 조정하겠다고 밝혔습니다.", "시범 운영", "정식으로 시작하기 전에 일정 기간 시험해 보는 것입니다."),
    ("새봄은행, 기준 대출금리 유지", "가상의 은행이 이번 달 기준 대출금리를 바꾸지 않았습니다.",
     "새봄은행은 매달 대출에 적용할 기본 금리를 정합니다.",
     "새봄은행은 이번 달 기준 대출금리를 지난달과 같은 수준으로 유지했습니다. 개별 고객의 실제 금리는 계약 조건에 따라 달라집니다.",
     "", "기준 대출금리", "은행이 대출 이자를 정할 때 기본으로 삼는 금리입니다."),
    ("온빛연구소, 재사용 배터리 실험 결과 공개", "사용한 배터리를 다른 용도로 쓸 수 있는지 시험했습니다.",
     "온빛연구소는 가상의 배터리 재사용 연구를 진행하고 있습니다.",
     "연구소는 회수한 배터리의 상태를 점검하고 소형 저장 장치로 활용하는 실험을 했다고 발표했습니다. 이번 결과는 실험 환경에서 나온 것으로 제품 출시를 뜻하지 않습니다.",
     "연구소는 안전성을 더 확인하기 위해 후속 시험이 필요하다고 설명했습니다.", "에너지 저장 장치", "전기를 모아 두었다가 필요할 때 꺼내 쓰는 장치입니다."),
    ("누리마을 도서관, 주말 개방 시간 확대", "평일 방문이 어려운 주민을 위해 주말에 더 오래 문을 엽니다.",
     "누리마을 도서관은 주말 운영 시간에 관한 주민 의견을 모았습니다.",
     "도서관은 다음 달부터 주말 운영 시간을 늘린다고 안내했습니다. 자료실별 세부 이용 시간은 도서관 안내에서 확인할 수 있습니다.",
     "", "", ""),
    ("가온학교, 일회용품 줄이기 실험 시작", "급식실에서 다회용 용기를 쓰는 작은 실험을 진행합니다.",
     "가온학교는 급식실에서 사용하는 일회용품을 줄이는 방법을 찾고 있습니다.",
     "학교는 일부 급식 공간에 다회용 용기를 도입해 사용량과 세척 과정을 확인할 계획입니다. 아직 실험 결과나 감소 효과는 확인되지 않았습니다.",
     "학교는 실험 이후 학생과 급식 담당자의 의견을 들을 예정이라고 밝혔습니다.", "다회용", "한 번 쓰고 버리지 않고 여러 번 사용할 수 있다는 뜻입니다."),
    ("마루시, 보행로 정비 계획 발표", "시민이 걷는 길의 불편한 구간을 먼저 정비합니다.",
     "마루시는 보행로의 파손 구간을 조사해 왔습니다.",
     "시는 조사 결과를 토대로 보행로 정비 계획을 발표했습니다. 공사 일정과 대상 구간은 추가 안내할 예정입니다.",
     "", "보행로", "차량보다 사람이 걸어 다니도록 마련한 길입니다."),
]
now = datetime.fromisoformat("2026-10-13T07:00:00+09:00")
publishers = ["가람일보 (가상)", "모아뉴스 (가상)", "온빛신문 (가상)"]
issues = []
for index, (title, line, background, current, reaction, term, definition) in enumerate(rows, 1):
    sources = [{"id": f"demo-{index}-{j}", "publisher": publisher, "title": title,
                "url": f"https://example.com/?demo-source={index}-{j}",
                "publishedAt": now.isoformat(), "independenceKey": f"fiction-{j}", "method": "demo"}
               for j, publisher in enumerate(publishers[:3 if index % 2 else 2], 1)]
    ids = [s["id"] for s in sources]
    def sentence(section, value):
        return {"id": f"s-{section}", "text": value, "kind": "fact", "attribution": None, "sourceIds": ids}
    issues.append({"id": f"demo-issue-{index:03}", "rank": index, "title": title, "oneLineSummary": line,
                   "titleSourceIds": ids, "summarySourceIds": ids,
                   "background": [sentence("background", background)],
                   "currentSituation": [sentence(f"current-{n}", value.rstrip(".") + ".") for n, value in enumerate(current.split(". ")) if value],
                   "response": [sentence("response", reaction)] if reaction else [],
                   "terminology": [{"term": term, "explanation": definition}] if term else [],
                   "sources": sources,
                   "ranking": {"method": "demo", "score": None, "reason": "화면 체험을 위해 편집한 가상 이슈입니다. 실제 보도량이나 사용자 관심도로 선정하지 않았습니다.", "components": {}, "missingMetrics": ["조회수", "댓글수", "인기 순위"]}})
edition = Edition.model_validate({"schemaVersion": 1, "mode": "demo", "date": now.date().isoformat(),
                                 "updatedAt": now.isoformat(), "collectionStartedAt": now.isoformat(),
                                 "windowStart": (now - timedelta(days=1)).isoformat(), "windowEnd": now.isoformat(),
                                 "timezone": "Asia/Seoul", "rankingMethod": "demo", "warnings": [], "issues": issues})
target = ROOT / "public/data/demo.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(edition.model_dump_json(indent=2), encoding="utf-8")
(ROOT / "data").mkdir(exist_ok=True)
(ROOT / "data/edition.schema.json").write_text(json.dumps(Edition.model_json_schema(), ensure_ascii=False, indent=2), encoding="utf-8")
print("Generated 6 fictional DEMO issues and the shared JSON Schema.")
