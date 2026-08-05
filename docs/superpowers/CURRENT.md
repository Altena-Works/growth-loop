# growth-loop — 現状

最終更新: 2026-08-05

## これは何か

Claude Code 用プラグイン。公式ハーネスに欠けている**閉じた学習ループ**だけを足す。仕事が終わる → 知見をスキルとプロファイルとして捕捉する → 捕捉物を棚卸しする → 古びたものを削除する。

Hermes Agent (Nous Research) の「built-in learning loop」と Claude Code の既存機能を突き合わせ、**カバーされていない差分だけ**を移植した。cron・サブエージェント編成・チャット面・端末バックエンド・MCP・compress/undo/retry・画像生成/TTS はすべて対象外で、README の Non-goals 表に理由込みで書いてある。組み込みを二重実装すると半端な系が二つできる。

## 現在の状態

**実装完了、実セッションで動作検証済み。`main` にマージ済み。**

- プラグインは仕様どおり**ちょうど13ファイル**（`tests/test_completeness.py` が機械的に保証）
- テスト **89/89 pass**（`python3 tests/run.py`）
- `claude plugin validate ./growth-loop` → Validation passed
- 未コミットの変更なし
- **push はしていない。GitHub リポジトリは未作成。**

### 実セッションで確認済み（2026-08-05）

`claude --plugin-dir` の headless モード（`-p`）で実際に走らせて確認した。合成テストでは証明できない部分がここで初めて通った。

| 項目 | 結果 |
|---|---|
| スキル登録 | `learn` `refine` `recall` `profile` の4つがモデルから見える |
| `journey` / `forget` がモデル一覧に出ない | 意図どおり（`disable-model-invocation`）。`/growth-loop:journey` でユーザーからは起動できる |
| **フックの端から端までの発火** | 30 tool calls / 30 edits / 異なるファイル5件を正確に記録し、ledger と nudge-state を書き出した |
| `${CLAUDE_PLUGIN_ROOT}` のフック内解決 | 解決している（Bash ツールでは空。フック/スキル置換専用の変数で環境変数ではない） |
| `gl-journey` の実行 | ツール許可を渡さない状態でも `allowed-tools` フロントマターにより承認なしで実行 |
| `gl-recall` の実行 | 3,429件のトランスクリプトを検索、`--days 365` への拡大も動作 |
| **nudge がモデルに到達** | 継続ターンでモデルが `Stop hook additional context:` の全文を逐語引用した |
| `profile` の書き込み | 差し替え先に `## Tooling` 配下で日付付きの1行を追記 |
| `learn` の書き込み | 差し替え先に `<slug>/SKILL.md` を生成し、パスと description の2つだけを報告 |
| **ループが閉じる** | `learn` が書いたスキルを `gl-journey` が列挙。書かれたスキルには実在の行き止まりを記した `What goes wrong` がある |

**この検証で `bin/` の PATH 不発を発見し、修正した**（下の「`bin/` は PATH に乗らない」節）。9タスク分のレビューをすり抜けた欠陥で、ユニットテストでは原理的に捕まらない種類のもの。

スキルの散文も実地で規律を見せた。棚卸し材料がゼロのとき `journey` は判定を捏造せず空判定として報告し、サンドボックスでスキル本文が読めなかった実行では「What goes wrong の厚い方へ統合するという比較を実行できていないので、重複なしの結論は覆りうる」と自ら限界を申告した。

### 残っている作業

対話 UI でしか見られないものが1つだけ:

```bash
cd /Users/kn/File/projects/claude/growth-loop
claude --plugin-dir ./growth-loop
```

- `/hooks` に `gl-nudge` が `Stop` と `SessionEnd` の両方に登録されて見えるか

ただしこれは表示の確認にすぎない。**フックが実際に発火して ledger に正しい統計を書くところまでは上表で確認済み**で、そちらのほうが強い証拠になっている。

## 構成

プロジェクトルートの下にプラグインを入れ子にしてある。仕様の検証コマンド `claude --plugin-dir ./growth-loop` がそのまま通り、「13ファイル厳守」も破らずに済むため。

```
claude/growth-loop/
├── growth-loop/            ← プラグイン本体（13ファイル）
│   ├── .claude-plugin/plugin.json
│   ├── README.md
│   ├── skills/{learn,refine,recall,profile,journey,forget}/SKILL.md
│   ├── agents/skill-author.md
│   ├── hooks/hooks.json
│   └── bin/{gl-recall,gl-nudge,gl-journey}
├── tests/                  ← 89テスト（出荷しない。14個目のファイルにならないよう外に置いてある）
└── docs/superpowers/
    ├── CURRENT.md          ← これ
    └── plans/2026-08-04-growth-loop.md
```

永続状態は `~/.claude/growth-loop/`（`profile.md` / `ledger.jsonl` / `nudge-state.json`）、`GROWTH_LOOP_HOME` で差し替え可能。蒸留されたスキルは `~/.claude/skills/<slug>/SKILL.md` に書かれる（プラグインを外しても残るように、外に置く）。

## 設計上の確定事項

実装中に検証・決定して、リポジトリの外に記録が残らないもの。

### フック配送の非対称性（2026-08-04 に live docs で検証）

`Stop` では exit 0 + JSON の `hookSpecificOutput.additionalContext` が、次のモデル呼び出し時の system reminder としてモデルに届く。**これが nudge の配送経路。** 仕様が懸念していた「transcript にしか出ない」フォールバックは不要だった。

`SessionEnd` は非対称で、stdout がモデルに届かず、そもそも次のモデル呼び出しがない。よってこちらは `systemMessage` で人間に出す。両イベントは cooldown を共有し、`Stop` の直後に `SessionEnd` が二重発火しない。

`Stop` で exit 2 や `decision` キーは**使わない**。エージェントに続行を強制して連続ブロック上限を焼くため。ターンを奪う nudge は nudge ではない。

### `bin/` は PATH に乗らない（2026-08-05、ライブセッションで実測して仕様の記述を撤回）

プラグインドキュメントは「プラグインが有効な間 `bin/` は Bash ツールの PATH に追加される」と書いており、README の Verify 節もそれを前提に `gl-recall` / `gl-journey` をベアコマンドとして書いていた。**実測では違った。**

```
$ gl-journey --stale 999 ; echo "EXIT=$?"
(eval):1: command not found: gl-journey
EXIT=127
```

`which gl-recall gl-nudge gl-journey` も全滅。マニフェストと `bin/` 配下のスクリプト1本だけを持つ使い捨ての最小プラグインでも同じ結果になったため、これは growth-loop 固有の不具合ではなく `--plugin-dir` 側の一般的な挙動だと確認済み。だが影響は growth-loop に集中する: `learn` は最初の一歩で `gl-journey` を走らせ、`recall` は `gl-recall` が全てで、`journey` と `forget` は両方とも `gl-journey` に依存している。ある実行では、失敗を報告する代わりにモデルが黙って別経路で同じ情報を取りに行っており、これは不具合そのものより悪い——失敗が握りつぶされて次に発見されなくなる。

**修正:** `${CLAUDE_PLUGIN_ROOT}` はスキルの Markdown 本文内で展開されることをプローブスキルで確認済みなので、`learn` / `recall` / `journey` / `forget` の4スキルにある `bin/` 呼び出しを全て `"${CLAUDE_PLUGIN_ROOT}"/bin/gl-journey` のような明示パスに書き換えた（ダブルクオート必須、パスに空白が入りうるため）。あわせて4スキルそれぞれに `allowed-tools: Bash("${CLAUDE_PLUGIN_ROOT}"/bin/<script>:*)` を追加——本文と `allowed-tools` の両方で同じ変数を使うことが、権限プロンプトなしでバンドル済みスクリプトを実行させる鍵になる。

この `allowed-tools` の効果は鵜呑みにせず実測で確認した。同一の `journey` スキルから `allowed-tools` 行だけを抜いたコントロール版プラグインを作り、`--allowedTools` も `--permission-mode` も付けない headless セッションで同じコマンドを走らせたところ、ツール呼び出しは `"This command requires approval"` で止まり、非対話セッションのため承認できずに実行されなかった。`allowed-tools` を戻すと同じコマンドが承認なしでそのまま実行された。フロントマターの効果は実在する。

`tests/test_skills.py` の既存アサーションは `"gl-journey"` / `"gl-recall"` という部分文字列一致だったため、明示パス化後もそのまま素通りしてしまい、この不具合を検出できずリグレッションも防げなかった。明示パスの完全な部分文字列を要求するように締め直し、4スキル全てに `allowed-tools` が実際に呼び出しパスをカバーしているかを検査するテストクラスを追加した。

### 書き込み先はスクリプトに解決させる（2026-08-05、ライブセッションで2度失敗して確定）

`learn` と `profile` は書き込み先を散文で名指ししていた。`learn` は `~/.claude/skills/<slug>/SKILL.md` を決め打ち、`profile` は「`~/.claude/growth-loop/profile.md`、`$GROWTH_LOOP_HOME` が設定されていればそちら」という併記。**どちらも実測で書き込みに失敗した。**

決め打ちの害は書き込み失敗だけではない。`gl-journey` の走査先を絞った際に `learn` 側を直さなかったため、`GROWTH_LOOP_SKILL_ROOTS` を設定すると `learn` の書き込み先と `gl-journey` の走査先がずれる。`learn` の第一歩は「`gl-journey` を走らせて重複を検出する」なので、自分が書いた場所を自分で見に行けなくなり、腐敗の入り口を塞ぐ仕組みがそこで止まる。

最初の修正では散文をシェル展開に置き換えた（`echo "${GROWTH_LOOP_HOME:-$HOME/.claude/growth-loop}/profile.md"`）。**これも実測で失敗した。** このユーザーの `settings.json` の PreToolUse フックが、シェル展開を含む Bash コマンドを `Contains expansion` で拒否する。そしてブロックされたモデルは、もっともらしいパスを推測して読み書きを試み、成功したように見える報告を返しながら実際には何も書かない。素の失敗より悪い。

**現在の方式:** `gl-journey --paths` が解決済みのパスを2行で出す。

```
skills-root: /Users/kn/.claude/skills
profile: /Users/kn/.claude/growth-loop/profile.md
```

`learn` と `profile` はこれを実行して結果を使う。解決は Python 側の1箇所だけで行われるので、走査先と書き込み先が構造的にずれない。スキル本文には「シェル展開で解決しようとするな」という理由付きの禁止も書いてある。

`forget` は `gl-journey` の出力から実パスを得るので構造的に正しく、`refine` はその場で編集するだけなので、どちらも対象外。

### gl-journey の走査範囲（仕様§5.6 からの意図的な逸脱）

仕様は走査先に `~/.claude/plugins` を含めていたが、**既定から外した。**

実機での実測: 列挙される SKILL.md 154件のうち146件が他社製プラグイン。しかも各プラグインは `cache/` と `marketplaces/` に二重チェックアウトされていて別 inode なので `resolve()` の重複排除をすり抜ける。結果、`journey` が消せないベンダーファイルに三択判定を強制し、`forget` の導線がインストール済みプラグインの削除を指し、`learn`（毎回いちばん先に `gl-journey` を走らせる）が19KBの他人の在庫をコンテキストに流し込んでいた。このプラグイン自身の設計原則と正面から衝突する。

現在の既定は `~/.claude/skills` と `./.claude/skills` の2つ。出力は 19,345 → 1,432 バイト。広く見たい場合は `GROWTH_LOOP_SKILL_ROOTS`（README に記載済み）。

### edit の判定（偽陽性と偽陰性を両方潰すのに2周かかった）

`EDIT_MARKERS` はツール名への部分文字列一致なので、当初 `TodoWrite` が `"write"` に一致していた。`Read`×22 + `TodoWrite`×3 という平凡な調査セッションで nudge が発火する状態で、設計が名指しで警戒していた habituation そのものだった。

修正で「入力が対象ファイルを名指しているときだけ edit と数える」に変えたが、`file_path` しか見ていなかったため今度は `NotebookEdit`（パラメータは `notebook_path`）が落ちた。現在は両方のキーを見る。実測マトリクス: `TodoWrite` / `NotebookRead` / `Read` / `WebSearch` は0件、`MultiEdit` / `Write` / `NotebookEdit` は計上。

**マーカー集合を広げるときの注意:** 対象ファイルのゲートは「対象を名指さないツール」を弾くだけで、対象を名指す読み取り専用ツールには無力。`NotebookRead` は `notebook_path` を、`Read` は `file_path` を持つ。この2つが今安全なのは、名前にマーカーが含まれていないからにすぎない。

### モデルが起動できないスキルへの経路

`journey` と `forget` は `disable-model-invocation: true`。棚卸しと削除は人間の決定で、自分の蓄積を黙って消せるモデルは信頼できないため。

`refine` と `journey` の本文は `/growth-loop:forget` へ「route せよ」と書くが、モデルからは起動できない。制約に触れずに放置すると、Write 権限を持つモデルが自分でディレクトリを消し、`forget` が存在する唯一の理由である「提示して確認を取る」ゲートを飛ばす分岐が残る。両方に「モデルからは起動できない、提示して止まれ」と明記済み。

### その他の検証結果

- スキルの `description` 上限は 1,024 ではなく **1,536 文字**（`description` + `when_to_use` の合算）
- `plugin.json` は現在オプション（未指定でも自動検出）だが、仕様§5.1 が要求するので同梱
- `hooks/hooks.json` はデフォルト探索位置。マニフェストに `hooks` キーを書くと conflicting-manifest エラーになる
- transcript root は実機では `~/.claude/projects` のみ存在（3,308件）。`~/.claude/sessions` は空、他3候補は不在。自動探索は全候補を残してある

## 既知の未対応（非ブロッキング）

- `gl-nudge:21` のコメント末尾が「対象ファイルのゲートがあればマーカー拡張は安全」と読める。一般には偽（上記参照）。現在の挙動の記述としては正しく、仮定の話を誤っているだけ
- `gl-nudge:31` の docstring が戻り値のリストを `[file_path, ...]` と呼んでいるが、`notebook_path` も入りうる

## 次にやるなら

1. `/hooks` の表示確認（残る唯一の未確認項目。発火自体は確認済みなので優先度は低い）
2. GitHub リポジトリ作成と push（**未承認。push は都度承認が要る**）
3. 実運用でしばらく使い、`MIN_TOOL_CALLS` / `MIN_EDITS` / `COOLDOWN_SECONDS` を体感に合わせる。README にも書いたが、緩めるのは「鳴ってほしかった」と思ってからにする。慣れてしまってから締め直しても habituation は戻らない
