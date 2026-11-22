# it-aptitude — IT適性診断（単一ファイル Flask）
#
# 目次
#   Unit 1: データ定義（能力問題・性格質問・職種重み・解説）
#   Unit 2: 採点ロジック
#   Unit 3: レーダーチャートSVG生成
#   Unit 4: 画面（CSS/JS/HTML生成）
#   Unit 5: ルーティング
#
# 質問・採点・解説文はすべて自作。回答はサーバーに保存しない（リクエスト内でのみ処理）。

from flask import Flask, request, redirect, url_for, render_template_string
import math

app = Flask(__name__)

# ============================================================
# Unit 1: データ定義
# ============================================================

# 知的能力4分野（キー, 表示名, 解説）
ABILITY_FIELDS = [
    ("count", "計数理解",
     "数や計算の関係を、速く正確に読み取る力。見積もりや集計の場面で土台になる。"),
    ("pattern", "直感的推理・法則性理解",
     "並びや記号の流れから、隠れた規則を見つけ出す力。仕様のパターンを掴む助けになる。"),
    ("prog", "プログラミング言語適応能力",
     "命令の並びを頭の中で実行し、変数や分岐の動きを追う力。コードを読む力に直結する。"),
    ("design", "システム設計・デバッグ能力",
     "表に出ている現象から、背後の構造や不具合の原因を推し量る力。"),
]

# 能力問題（全12問・各分野3問）。answer は choices のインデックス。
ABILITY_QUESTIONS = [
    # 計数理解
    {"field": "count",
     "q": "数列 2, 6, 12, 20, 30, □ の □ に入る数はいくつでしょう。",
     "choices": ["36", "40", "42", "44"], "answer": 2},
    {"field": "count",
     "q": "ある商品を2割引で買うと 960 円でした。割引前の値段はいくらでしょう。",
     "choices": ["1,150円", "1,200円", "1,250円", "1,280円"], "answer": 1},
    {"field": "count",
     "q": "5人で作業すると8日かかる仕事があります。同じペースの8人で作業すると何日かかるでしょう。",
     "choices": ["4日", "5日", "6日", "13日"], "answer": 1},
    # 直感的推理・法則性理解
    {"field": "pattern",
     "q": "文字列の並び AB, BC, CD, DE, □ の □ に入るのはどれでしょう。",
     "choices": ["EF", "FG", "EA", "DF"], "answer": 0},
    {"field": "pattern",
     "q": "記号の並び「○△□ / ○○△△□□ / ○○○△△△□□□」と続くとき、4番目のグループに出てくる ○ の数はいくつでしょう。",
     "choices": ["3", "4", "5", "6"], "answer": 1},
    {"field": "pattern",
     "q": "A=1, B=2, C=3, …, Z=26 と対応させるとき、CAT の文字の数の合計はいくつでしょう。",
     "choices": ["22", "24", "26", "27"], "answer": 1},
    # プログラミング言語適応能力
    {"field": "prog",
     "q": "次の手順を実行したあと、y の値はいくつでしょう。手順: x=3 とする／y=5 とする／x に y の値を入れる／y に x の値を入れる",
     "choices": ["3", "5", "8", "エラーになる"], "answer": 1},
    {"field": "prog",
     "q": "「合計=0 とする／数=1 から 4 まで 1 ずつ増やしながら、合計 に 数 を足す」を実行したあと、合計 の値はいくつでしょう。",
     "choices": ["4", "9", "10", "24"], "answer": 2},
    {"field": "prog",
     "q": "点数=75 のとき、「点数が80以上なら『優』、そうでなく60以上なら『良』、それ以外は『可』」という判定の結果はどれでしょう。",
     "choices": ["優", "良", "可", "エラーになる"], "answer": 1},
    # システム設計・デバッグ能力
    {"field": "design",
     "q": "1から10までの合計を求めるプログラムで、繰り返しの範囲が誤って「1から9まで」になっていました。正しい結果と比べてどうなるでしょう。",
     "choices": ["同じ結果になる", "10少なくなる", "10多くなる", "0になる"], "answer": 1},
    {"field": "design",
     "q": "利用者が増えて処理が遅くなったシステムがあります。改善の最初の一手として最も適切なのはどれでしょう。",
     "choices": ["すぐにサーバーを増やす", "どこに時間がかかっているか計測して原因を特定する",
                 "プログラムを全部書き直す", "しばらく様子を見る"], "answer": 1},
    {"field": "design",
     "q": "「たまにだけ起きる」不具合の報告がありました。最初にすべきことはどれでしょう。",
     "choices": ["とりあえず再起動する", "起きる条件（再現手順）を記録して特定する",
                 "関係しそうな箇所を全部直す", "利用者の操作ミスと判断する"], "answer": 1},
]

# パーソナリティ9項目（キー, 表示名, 解説, 面接想定質問, 帯コメント 高/中/低）
TRAITS = [
    ("vitality", "ヴァイタリティ",
     "体力・気力に優れ、新しいことへ踏み出す推進力。",
     ["困難な状況でもやり遂げた経験を教えてください", "新しいことに挑戦した経験はありますか"],
     ("前に出る力強さがあり、場面を動かす側に回れるタイプです。",
      "場面によって推進力を出せるタイプです。",
      "慎重に様子を見るタイプです。無理のない範囲から一歩ずつが合いそうです。")),
    ("affability", "人あたり",
     "人に対してよい印象を与え、過度な防衛心を起こさせない態度がとれること。",
     ["相手と意見が合わなかったとき、どう伝えましたか", "人から相談されたとき、心がけていることはありますか"],
     ("初対面でも距離を縮めるのが早く、窓口や調整の場面で力を出しやすいタイプです。",
      "相手に合わせて柔らかく接することができるタイプです。",
      "人と接する場面では緊張しやすいタイプです。少人数の関係から築くのが合いそうです。")),
    ("teamwork", "チームワーク",
     "チームにうまく溶け込み、摩擦を起こさずに物事を処理できること。",
     ["チームで協力して成果を出した経験を話してください", "チームで困っている人がいたらどうしますか"],
     ("周りと足並みをそろえるのが上手く、協力の中心になれるタイプです。",
      "協力しながら進めることができるタイプです。",
      "自分のペースを大事にするタイプです。役割がはっきりした分担が合いそうです。")),
    ("creativity", "創造的思考力",
     "新しいコンセプトを作り出す力。定型的な思考方法をとらない柔軟さ。",
     ["自分で工夫して改善した経験を教えてください", "前例のない課題にどう取り組みますか"],
     ("新しいやり方を考えるのが得意で、改善や企画の場面で力を出しやすいタイプです。",
      "必要に応じて工夫を考えられるタイプです。",
      "決まった手順に沿って進めるほうが力を出せるタイプです。")),
    ("problem", "問題解決力",
     "筋の通ったものの見方ができ、合理的に推論して問題を解く力。",
     ["難しい問題をどう解いたか、順序立てて教えてください", "原因が分からない問題にどう向き合いますか"],
     ("原因の切り分けが速く、難しい課題ほど燃えるタイプです。",
      "筋道を立てて考えれば取り組めるタイプです。",
      "手がかりが多い課題から取り組むと力を出しやすいタイプです。")),
    ("adaptability", "状況適応力",
     "状況に合わせて行動し、自分の行動を客観的に眺められること。",
     ["急な変更に対応した経験を教えてください", "新しい環境に慣れるために工夫したことはありますか"],
     ("変化への切り替えが早く、想定外の場面でも立て直せるタイプです。",
      "変化にも順応していけるタイプです。",
      "見通しが立った環境のほうが力を出せるタイプです。")),
    ("pressure", "プレッシャーへの耐力",
     "プレッシャーを上手に扱うことができ、感情に支配されないこと。",
     ["締切が厳しい状況をどう乗り越えましたか", "失敗したとき、次にどう活かしましたか"],
     ("追い込まれた場面でも平静さを保てるタイプです。",
      "緊張と付き合いながら進められるタイプです。",
      "余裕のある進め方のほうが力を出せるタイプです。")),
    ("organize", "オーガナイズ能力",
     "計画を立てたり人を配置したりすることがうまく、細部のツメに甘さを残さないこと。",
     ["複数の作業をどう整理して進めますか", "計画が崩れたとき、どう立て直しますか"],
     ("段取りと抜け漏れチェックが得意で、進行管理に向くタイプです。",
      "段取りを考えながら進められるタイプです。",
      "まず動いてから整えるタイプです。チェックリスト等の道具と相性がよさそうです。")),
    ("leadership", "統率力",
     "メンバーの動きに注意を払い、自分から働きかけてやる気を起こさせることができること。",
     ["人をまとめた経験を教えてください", "メンバーに指示を出すとき気をつけていることはありますか"],
     ("まとめ役を引き受けられるタイプです。周りを動かす場面で力を出せます。",
      "必要に応じてまとめ役を担えるタイプです。",
      "支える側の役割で力を出すタイプです。")),
]

# 性格質問（全27問・各項目3問）。reverse=True は逆転項目。
PERSONALITY_QUESTIONS = [
    {"trait": "vitality", "text": "新しいことに挑戦するとき、多少のリスクがあってもまず動いてみるほうだ", "reverse": False},
    {"trait": "vitality", "text": "忙しい日が続いても、やる気が落ちにくいほうだ", "reverse": False},
    {"trait": "vitality", "text": "失敗しても、気持ちを切り替えて次に進めるほうだ", "reverse": False},
    {"trait": "affability", "text": "初対面の人とも、緊張せずに話し始めることができる", "reverse": False},
    {"trait": "affability", "text": "相手の立場や気持ちを考えてから言葉を選ぶほうだ", "reverse": False},
    {"trait": "affability", "text": "人から相談されると、面倒がらずに耳を傾けるほうだ", "reverse": False},
    {"trait": "teamwork", "text": "自分の担当でなくても、困っているメンバーがいれば手伝うほうだ", "reverse": False},
    {"trait": "teamwork", "text": "意見が分かれたときは、落としどころを探すほうだ", "reverse": False},
    {"trait": "teamwork", "text": "人と足並みをそろえるより、自分のペースで進めるほうが気楽だ", "reverse": True},
    {"trait": "creativity", "text": "決まった手順がない場面では、自分でやり方を考えるのが楽しい", "reverse": False},
    {"trait": "creativity", "text": "既存のやり方に「別の方法はないか」と考えることが多い", "reverse": False},
    {"trait": "creativity", "text": "思いついたアイデアを、とりあえず形にしてみたくなるほうだ", "reverse": False},
    {"trait": "problem", "text": "問題が起きたら、まず原因を切り分けてから対処するほうだ", "reverse": False},
    {"trait": "problem", "text": "分からないことも、筋道を立てて考えれば大抵たどり着けると思う", "reverse": False},
    {"trait": "problem", "text": "難しい課題ほど、分解して小さくしてから取り組むほうだ", "reverse": False},
    {"trait": "adaptability", "text": "予定や仕様が急に変わっても、気持ちを切り替えて対応できるほうだ", "reverse": False},
    {"trait": "adaptability", "text": "環境やルールが変わることに、あまり抵抗を感じない", "reverse": False},
    {"trait": "adaptability", "text": "想定外のことが起きても、慌てずに優先順位をつけ直せるほうだ", "reverse": False},
    {"trait": "pressure", "text": "締切が迫っていても、落ち着いて作業を続けられるほうだ", "reverse": False},
    {"trait": "pressure", "text": "厳しい指摘を受けても、感情的にならずに受け止められるほうだ", "reverse": False},
    {"trait": "pressure", "text": "大事な発表の前は、緊張で本来の力が出せないことが多い", "reverse": True},
    {"trait": "organize", "text": "作業を始めるときは、まず段取りと優先順位を決めるほうだ", "reverse": False},
    {"trait": "organize", "text": "抜けや漏れがないよう、チェックしながら進めるほうだ", "reverse": False},
    {"trait": "organize", "text": "計画を細かく立てるより、始めてから考えるほうが多い", "reverse": True},
    {"trait": "leadership", "text": "グループでは、自分からまとめ役を引き受けることが多い", "reverse": False},
    {"trait": "leadership", "text": "メンバーに作業をお願いしたり、進み具合を確認したりするのが苦にならない", "reverse": False},
    {"trait": "leadership", "text": "決断が必要な場面では、自分で判断して周りに示すほうだ", "reverse": False},
]

# IT職種（キー, 略称, 表示名, 重み {能力キー or 性格キー: 重み}）
JOBS = [
    ("pg", "PG", "プログラマー",
     {"prog": 0.45, "count": 0.20, "problem": 0.20, "creativity": 0.15}),
    ("ce", "CE", "カスタマーエンジニア",
     {"affability": 0.30, "adaptability": 0.30, "problem": 0.20, "count": 0.20}),
    ("se", "SE", "システムエンジニア",
     {"design": 0.40, "pattern": 0.20, "organize": 0.20, "problem": 0.20}),
    ("pm", "PM", "プロジェクトマネージャー",
     {"leadership": 0.35, "organize": 0.30, "affability": 0.20, "vitality": 0.15}),
]

# 総合判定ランク（下限スコア, ランク, 一言）
RANKS = [
    (80, "S", "IT職に非常に適性がある"),
    (65, "A", "IT職に適性がある"),
    (50, "B", "IT職に向いている面が多い"),
    (35, "C", "伸ばし方次第で伸びるタイプ"),
    (0, "D", "適性をこれから探していく段階"),
]

LIKERT_LABELS = ["とてもあてはまる", "ややあてはまる", "どちらともいえない",
                 "あまりあてはまらない", "まったくあてはまらない"]

# ============================================================
# Unit 2: 採点ロジック
# ============================================================

def score_answers(ability_answers, personality_answers):
    """ability_answers: {index: choice_index}, personality_answers: {index: 1..5}
    戻り値: dict(ability={field_key: 0..100}, traits={trait_key: 0..100},
                jobs=[(key, abbr, name, score)], overall, rank, rank_comment)"""
    # 能力: 分野ごとに正解率(%)
    ability = {}
    for key, _name, _desc in ABILITY_FIELDS:
        qs = [q for q in ABILITY_QUESTIONS if q["field"] == key]
        correct = sum(1 for i, q in enumerate(ABILITY_QUESTIONS)
                      if q["field"] == key and ability_answers.get(i) == q["answer"])
        ability[key] = round(correct / len(qs) * 100) if qs else 0

    # 性格: 項目ごとに 3問合計(3..15) を 0..100 へ
    traits = {}
    for key, _name, _desc, _qs, _bands in TRAITS:
        qs = [(i, q) for i, q in enumerate(PERSONALITY_QUESTIONS) if q["trait"] == key]
        total = 0
        for i, q in qs:
            v = personality_answers.get(i, 3)
            if q["reverse"]:
                v = 6 - v
            total += v
        traits[key] = round((total - 3) / 12 * 100) if qs else 0

    merged = dict(ability)
    merged.update(traits)

    jobs = []
    for key, abbr, name, weights in JOBS:
        s = sum(merged[src] * w for src, w in weights.items())
        jobs.append((key, abbr, name, round(s)))

    overall = round(sum(j[3] for j in jobs) / len(jobs)) if jobs else 0
    rank, rank_comment = RANKS[-1][1], RANKS[-1][2]
    for threshold, r, c in RANKS:
        if overall >= threshold:
            rank, rank_comment = r, c
            break

    return {"ability": ability, "traits": traits, "jobs": jobs,
            "overall": overall, "rank": rank, "rank_comment": rank_comment}


def band_of(score):
    """スコア帯: 0=低, 1=中, 2=高"""
    if score >= 67:
        return 2
    if score >= 34:
        return 1
    return 0


# ============================================================
# Unit 3: レーダーチャートSVG生成
# ============================================================

def radar_svg(trait_scores):
    """trait_scores: TRAITS の順序どおりの 0..100 リスト。9軸レーダーをSVG文字列で返す。"""
    cx, cy, r_max = 170, 160, 115
    n = len(trait_scores)

    def point(i, ratio):
        ang = -math.pi / 2 + 2 * math.pi * i / n
        return (cx + r_max * ratio * math.cos(ang), cy + r_max * ratio * math.sin(ang))

    parts = ['<svg viewBox="0 0 340 320" class="radar" role="img" aria-label="パーソナリティ レーダーチャート">']
    # グリッド（25/50/75/100%）
    for ratio in (0.25, 0.5, 0.75, 1.0):
        pts = " ".join(f"{point(i, ratio)[0]:.1f},{point(i, ratio)[1]:.1f}" for i in range(n))
        parts.append(f'<polygon points="{pts}" class="radar-grid"/>')
    # 軸
    for i in range(n):
        x, y = point(i, 1.0)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" class="radar-axis"/>')
    # データ
    pts = " ".join(f"{point(i, trait_scores[i] / 100)[0]:.1f},{point(i, trait_scores[i] / 100)[1]:.1f}"
                   for i in range(n))
    parts.append(f'<polygon points="{pts}" class="radar-data"/>')
    for i in range(n):
        x, y = point(i, trait_scores[i] / 100)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" class="radar-dot"/>')
    # ラベル
    for i, (_k, name, *_rest) in enumerate(TRAITS):
        x, y = point(i, 1.18)
        anchor = "middle"
        if x < cx - 30:
            anchor = "end"
        elif x > cx + 30:
            anchor = "start"
        parts.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" class="radar-label">{name}</text>')
    parts.append("</svg>")
    return "".join(parts)

# ============================================================
# Unit 4: 画面（CSS/JS/HTML生成）
# ============================================================

CSS = """
:root{--bg:#f6f7f9;--card:#ffffff;--text:#1c2430;--muted:#5b6b7f;--line:#d8dee7;
--accent:#1f7a4d;--accent2:#2b6cb0;--bar:#38a169;--warn:#b7791f}
html[data-theme="dark"]{--bg:#14181f;--card:#1e242f;--text:#e8edf3;--muted:#9fb0c3;--line:#39424f;
--accent:#4cc38a;--accent2:#63b3ed;--bar:#4cc38a;--warn:#e5c07b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font-family:"Hiragino Kaku Gothic ProN","Hiragino Sans","Noto Sans JP",sans-serif;line-height:1.7}
.wrap{max-width:860px;margin:0 auto;padding:20px 16px 48px}
header.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
h1{font-size:1.5rem;margin:.4em 0}
h2{font-size:1.15rem;border-left:5px solid var(--accent);padding-left:.5em;margin:1.4em 0 .6em}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;margin:14px 0}
button,.btn{display:inline-block;background:var(--accent);color:#fff;border:none;border-radius:8px;
padding:12px 28px;font-size:1rem;cursor:pointer;text-decoration:none}
button.ghost,.btn.ghost{background:transparent;color:var(--accent);border:1px solid var(--accent)}
fieldset{border:1px solid var(--line);border-radius:10px;margin:14px 0;padding:14px 16px}
legend{font-weight:700;padding:0 .4em}
.q{margin:10px 0}
.q p{margin:.2em 0 .4em}
label.opt{display:block;padding:6px 10px;border:1px solid var(--line);border-radius:8px;margin:5px 0;cursor:pointer}
label.opt:hover{border-color:var(--accent)}
.likert{display:flex;gap:6px;flex-wrap:wrap}
.likert label{flex:1;min-width:100px;text-align:center;padding:8px 4px;border:1px solid var(--line);
border-radius:8px;cursor:pointer;font-size:.86rem}
.rank{font-size:3.2rem;font-weight:800;color:var(--accent);line-height:1}
.bar-row{display:flex;align-items:center;gap:10px;margin:8px 0}
.bar-row .name{width:210px;font-size:.95rem}
.bar-track{flex:1;background:var(--line);border-radius:6px;height:16px;overflow:hidden}
.bar-fill{height:100%;background:var(--bar)}
.bar-pct{width:52px;text-align:right;font-weight:700}
.radar{width:100%;max-width:420px;display:block;margin:0 auto}
.radar-grid{fill:none;stroke:var(--line)}
.radar-axis{stroke:var(--line)}
.radar-data{fill:rgba(56,161,105,.35);stroke:var(--bar);stroke-width:2}
.radar-dot{fill:var(--bar)}
.radar-label{fill:var(--text);font-size:11px}
.muted{color:var(--muted);font-size:.9rem}
.error{background:#fff5f5;border:1px solid #e53e3e;color:#9b2c2c;border-radius:8px;padding:10px 14px}
html[data-theme="dark"] .error{background:#3a2323;color:#feb2b2}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:640px){.grid2{grid-template-columns:1fr}.bar-row .name{width:130px}}
"""

JS = """
(function(){
  var saved = null;
  try { saved = localStorage.getItem('it-aptitude-theme'); } catch (e) {}
  if (saved) { document.documentElement.setAttribute('data-theme', saved); }
  var btn = document.getElementById('theme-toggle');
  if (btn) {
    btn.addEventListener('click', function(){
      var cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', cur);
      try { localStorage.setItem('it-aptitude-theme', cur); } catch (e) {}
    });
  }
  var form = document.getElementById('quiz-form');
  if (form) {
    form.addEventListener('submit', function(ev){
      var groups = {};
      form.querySelectorAll('input[type="radio"]').forEach(function(r){ groups[r.name] = groups[r.name] || r.checked; if (r.checked) groups[r.name] = true; });
      var missing = Object.keys(groups).filter(function(k){ return !groups[k]; });
      if (missing.length > 0) {
        ev.preventDefault();
        var box = document.getElementById('form-error');
        if (box) { box.style.display = 'block'; box.textContent = '未回答の質問が ' + missing.length + ' 件あります。すべて回答してから結果を見てください。'; box.scrollIntoView(); }
      }
    });
  }
})();
"""

BASE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<style>{{ css|safe }}</style>
</head>
<body>
<div class="wrap">
<header class="top">
<div><strong>IT適性診断</strong></div>
<button type="button" id="theme-toggle" class="ghost" style="padding:6px 14px">テーマ切替</button>
</header>
{{ body|safe }}
<footer class="muted" style="margin-top:32px">
<p>この診断は、質問・採点・解説を独自に設計した参考用のツールです。結果は絶対的な判定ではなく、進路や役割を考えるときの材料としてご利用ください。回答はサーバーに保存されません。</p>
</footer>
</div>
<script>{{ script|safe }}</script>
</body>
</html>"""


def page(title, body):
    return render_template_string(BASE, title=title, css=CSS, script=JS, body=body)


def index_body():
    return """
<h1>IT適性診断</h1>
<div class="card">
<p>ITの仕事への適性を、<strong>知的能力（全12問）</strong>と<strong>パーソナリティ（全27問）</strong>の合計39問で診断します。</p>
<ul>
<li>総合判定（S〜Dランク）</li>
<li>IT職種別の適職度（PG／CE／SE／PM）</li>
<li>パーソナリティ9項目のレーダーチャートと解説</li>
<li>強みにもとづく面接での想定質問</li>
</ul>
<p class="muted">所要時間の目安は10分ほどです。性格の質問に正解・不正解はありません。思ったままに答えてください。</p>
<p><a class="btn" href="/quiz">診断をはじめる</a></p>
</div>
"""


def quiz_body(error=False):
    parts = []
    parts.append("<h1>IT適性診断 — 質問</h1>")
    if error:
        parts.append('<p class="error">未回答の質問があります。すべて回答してから結果を見てください。</p>')
    parts.append('<p id="form-error" class="error" style="display:none"></p>')
    parts.append('<form id="quiz-form" method="post" action="/result">')

    parts.append("<h2>第1部：知的能力（12問）</h2>")
    current_field = None
    for i, q in enumerate(ABILITY_QUESTIONS):
        if q["field"] != current_field:
            current_field = q["field"]
            fname = next(n for k, n, _d in ABILITY_FIELDS if k == current_field)
            parts.append(f"<fieldset><legend>{fname}</legend>")
        parts.append(f'<div class="q"><p>Q{i + 1}. {q["q"]}</p>')
        for ci, choice in enumerate(q["choices"]):
            req = " required" if ci == 0 else ""
            parts.append(f'<label class="opt"><input type="radio" name="a{i}" value="{ci}"{req}> {choice}</label>')
        parts.append("</div>")
        # 分野の最後の設問で fieldset を閉じる
        nxt = ABILITY_QUESTIONS[i + 1]["field"] if i + 1 < len(ABILITY_QUESTIONS) else None
        if nxt != current_field:
            parts.append("</fieldset>")

    parts.append("<h2>第2部：パーソナリティ（27問）</h2>")
    parts.append('<p class="muted">それぞれの文について、いちばん近いものを選んでください。</p>')
    parts.append("<fieldset><legend>パーソナリティ</legend>")
    for i, q in enumerate(PERSONALITY_QUESTIONS):
        parts.append(f'<div class="q"><p>Q{i + 1}. {q["text"]}</p><div class="likert">')
        for v in range(5, 0, -1):
            req = " required" if v == 5 else ""
            parts.append(f'<label><input type="radio" name="p{i}" value="{v}"{req}> {LIKERT_LABELS[5 - v]}</label>')
        parts.append("</div></div>")
    parts.append("</fieldset>")
    parts.append('<p><button type="submit">結果を見る</button></p>')
    parts.append("</form>")
    return "".join(parts)


def result_body(result, ability_answers):
    traits = result["traits"]
    jobs_sorted = sorted(result["jobs"], key=lambda j: j[3], reverse=True)
    top_job = jobs_sorted[0]
    top_traits = sorted(TRAITS, key=lambda t: traits[t[0]], reverse=True)[:2]

    parts = []
    parts.append("<h1>診断結果</h1>")

    # 総合判定＋適職
    parts.append('<div class="card grid2"><div>')
    parts.append('<p class="muted">あなたのIT適性（総合判定）</p>')
    parts.append(f'<div class="rank">{result["rank"]}</div>')
    parts.append(f'<p>{result["rank_comment"]}（総合スコア {result["overall"]}）</p>')
    parts.append("</div><div>")
    parts.append('<p class="muted">IT適職</p>')
    parts.append(f'<p style="font-size:1.2rem"><strong>{top_job[2]}</strong>（適職度 {top_job[3]}%）</p>')
    rest = "、".join(f'{j[2]} {j[3]}%' for j in jobs_sorted[1:])
    parts.append(f'<p class="muted">その他の職種：{rest}</p>')
    parts.append("</div></div>")

    # 職種別バー
    parts.append('<div class="card"><h2>IT職種別の適職度</h2>')
    for _k, abbr, name, s in result["jobs"]:
        parts.append(f'<div class="bar-row"><div class="name">{abbr} {name}</div>'
                     f'<div class="bar-track"><div class="bar-fill" style="width:{s}%"></div></div>'
                     f'<div class="bar-pct">{s}%</div></div>')
    parts.append("</div>")

    # 能力の正誤と分野別スコア
    parts.append('<div class="card"><h2>診断結果：知的能力</h2>')
    for key, name, desc in ABILITY_FIELDS:
        s = result["ability"][key]
        parts.append(f'<div class="bar-row"><div class="name">{name}</div>'
                     f'<div class="bar-track"><div class="bar-fill" style="width:{s}%"></div></div>'
                     f'<div class="bar-pct">{s}%</div></div>')
        parts.append(f'<p class="muted">{desc}</p>')
    parts.append("<details><summary>能力問題の正解とあなたの回答</summary>")
    for i, q in enumerate(ABILITY_QUESTIONS):
        fname = next(n for k, n, _d in ABILITY_FIELDS if k == q["field"])
        yours = ability_answers.get(i)
        mark = "正解" if yours == q["answer"] else "不正解"
        ytxt = q["choices"][yours] if yours is not None else "未回答"
        parts.append(f'<p>Q{i + 1}（{fname}）：{q["q"]}<br>正解：{q["choices"][q["answer"]]} ／ あなたの回答：{ytxt}（{mark}）</p>')
    parts.append("</details></div>")

    # パーソナリティ
    parts.append('<div class="card"><h2>診断結果：パーソナリティ</h2>')
    parts.append(radar_svg([traits[t[0]] for t in TRAITS]))
    for key, name, desc, _qs, bands in TRAITS:
        s = traits[key]
        parts.append(f'<div class="bar-row"><div class="name">{name}</div>'
                     f'<div class="bar-track"><div class="bar-fill" style="width:{s}%"></div></div>'
                     f'<div class="bar-pct">{s}%</div></div>')
        parts.append(f'<p class="muted">{desc} — {bands[band_of(s)]}</p>')
    parts.append("</div>")

    # 面接想定質問（上位2項目）
    parts.append('<div class="card"><h2>面接での想定質問（強み上位2項目）</h2>')
    for key, name, _desc, qs, _bands in top_traits:
        parts.append(f"<p><strong>{name}</strong></p><ul>")
        for q in qs:
            parts.append(f"<li>{q}</li>")
        parts.append("</ul>")
    parts.append("</div>")

    parts.append('<p><a class="btn ghost" href="/quiz">もう一度診断する</a> '
                 '<a class="btn ghost" href="/">トップへ</a></p>')
    return "".join(parts)


# ============================================================
# Unit 5: ルーティング
# ============================================================

@app.route("/")
def index():
    return page("IT適性診断", index_body())


@app.route("/quiz")
def quiz():
    return page("IT適性診断 — 質問", quiz_body(error=request.args.get("error") == "1"))


@app.route("/result", methods=["POST"])
def result():
    ability_answers = {}
    personality_answers = {}
    for i in range(len(ABILITY_QUESTIONS)):
        v = request.form.get(f"a{i}")
        if v is None:
            return redirect(url_for("quiz", error=1))
        ability_answers[i] = int(v)
    for i in range(len(PERSONALITY_QUESTIONS)):
        v = request.form.get(f"p{i}")
        if v is None:
            return redirect(url_for("quiz", error=1))
        personality_answers[i] = int(v)
    result = score_answers(ability_answers, personality_answers)
    return page("IT適性診断 — 結果", result_body(result, ability_answers))


@app.route("/healthz")
def healthz():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
