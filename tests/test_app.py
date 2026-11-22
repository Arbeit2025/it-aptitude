import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as m


def client():
    return m.app.test_client()


def full_form(ability_choice, personality_value):
    form = {}
    for i, q in enumerate(m.ABILITY_QUESTIONS):
        form[f"a{i}"] = str(ability_choice(q))
    for i in range(len(m.PERSONALITY_QUESTIONS)):
        form[f"p{i}"] = str(personality_value)
    return form


def test_data_integrity():
    assert len(m.ABILITY_QUESTIONS) == 12
    assert len(m.PERSONALITY_QUESTIONS) == 27
    for key, _n, _d in m.ABILITY_FIELDS:
        assert sum(1 for q in m.ABILITY_QUESTIONS if q["field"] == key) == 3
    for key, *_rest in m.TRAITS:
        assert sum(1 for q in m.PERSONALITY_QUESTIONS if q["trait"] == key) == 3
    for _k, _a, _n, weights in m.JOBS:
        assert abs(sum(weights.values()) - 1.0) < 1e-9
    for q in m.ABILITY_QUESTIONS:
        assert 0 <= q["answer"] < len(q["choices"])


def test_index_and_quiz():
    c = client()
    r = c.get("/")
    assert r.status_code == 200
    assert "IT適性診断" in r.get_data(as_text=True)
    r = c.get("/quiz")
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert 'name="a0"' in body and 'name="a11"' in body
    assert 'name="p0"' in body and 'name="p26"' in body
    assert body.count("<fieldset>") == body.count("</fieldset>")


def test_healthz():
    r = client().get("/healthz")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"


def test_result_all_correct_high_personality():
    c = client()
    r = c.post("/result", data=full_form(lambda q: q["answer"], 5))
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "診断結果" in body
    assert 'class="rank">S<' in body or 'class="rank">A<' in body
    assert "radar" in body  # レーダーSVG
    assert "面接での想定質問" in body


def test_result_all_wrong_low_personality():
    c = client()
    r = c.post("/result", data=full_form(lambda q: (q["answer"] + 1) % len(q["choices"]), 1))
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert 'class="rank">D<' in body


def test_result_missing_redirects():
    c = client()
    r = c.post("/result", data={"a0": "0"})
    assert r.status_code == 302
    assert "/quiz" in r.headers["Location"]


def test_scoring_reverse_items():
    # 全て「5（とてもあてはまる）」→ 逆転項目のある teamwork/pressure/organize は 67、他は 100
    res = m.score_answers({}, {i: 5 for i in range(len(m.PERSONALITY_QUESTIONS))})
    assert res["traits"]["teamwork"] == 67
    assert res["traits"]["pressure"] == 67
    assert res["traits"]["organize"] == 67
    assert res["traits"]["vitality"] == 100
    # 全て「1」→ 逆転項目のある項目は 33、他は 0
    res = m.score_answers({}, {i: 1 for i in range(len(m.PERSONALITY_QUESTIONS))})
    assert res["traits"]["teamwork"] == 33
    assert res["traits"]["vitality"] == 0


def test_script_not_escaped():
    # render_template_string で {{ script|safe }} を使わないと引用符が &#39; に化けてJSが死ぬ回帰防止
    body = client().get("/").get_data(as_text=True)
    assert "localStorage.getItem('it-aptitude-theme')" in body
    assert "&#39;" not in body
    assert "&#34;" not in body
