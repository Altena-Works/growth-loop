# growth-loop — 現状

最終更新: 2026-08-06

## これは何か

Claude Code 用プラグイン。公式ハーネスに欠けている**閉じた学習ループ**だけを足す。仕事が終わる → 知見をスキルとプロファイルとして捕捉する → 捕捉物を棚卸しする → 古びたものを削除する。

Hermes Agent (Nous Research) の「built-in learning loop」と Claude Code の既存機能を突き合わせ、**カバーされていない差分だけ**を移植した。cron・サブエージェント編成・チャット面・端末バックエンド・MCP・compress/undo/retry・画像生成/TTS はすべて対象外で、README の Non-goals 表に理由込みで書いてある。組み込みを二重実装すると半端な系が二つできる。

## 現在の状態

**実装完了、実セッションで動作検証済み。`main` にマージ済み。**

- プラグインは仕様どおり**ちょうど13ファイル**（`tests/test_completeness.py` が機械的に保証）
- テスト **123/123 pass**（`python3 tests/run.py`）
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
├── tests/                  ← 123テスト（出荷しない。14個目のファイルにならないよう外に置いてある）
└── docs/superpowers/
    ├── CURRENT.md          ← これ
    └── plans/2026-08-04-growth-loop.md
```

永続状態は `~/.claude/growth-loop/`（`profile.md` / `ledger.jsonl` / `nudge-state.json`）、`GROWTH_LOOP_HOME` で差し替え可能。蒸留されたスキルの書き込み先は `gl-journey --paths` が解決する（既定は `~/.claude/skills/<slug>/SKILL.md`）。プラグインを外しても残るように、外に置いてある。

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

### 検証手順そのものがプラグインを汚す（2026-08-06）

仕様§7の検証手順の1番目は `python3 -m py_compile growth-loop/bin/*`。これは `bin/__pycache__/` を書き、**13ファイル厳守のプラグインに3ファイル増える**。そして `test_completeness.py` は `__pycache__` を除外して数えていたので、汚染されていても「13ファイル」と報告していた。手順どおり検証した人ほど汚れ、テストは問題なしと言う。

`__pycache__` の存在自体を検査するテストを追加し、実際に汚してから落ちることを確認済み。README には書き込みを伴わない構文チェックを載せた:

```bash
python3 -c 'import ast,sys; [ast.parse(open(f).read()) for f in sys.argv[1:]]' bin/*
```

### 全経路の実地確認（2026-08-06）

一度も実際に動かしていなかった経路を、fixture を植えて一巡した。植えたのは古いスキル2本（200日・150日）、内容が重複するペア1組、誤ったコマンドを含むスキル1本。

| 経路 | 結果 |
|---|---|
| `journey` の三択判定 | 200日のスキルに「検証して修正」、150日に「維持」を出し、維持の理由を「`logrotate -f` は十年安定で、非 root 時の無言失敗は今も真」と述べた。古さだけで削除に倒さない |
| `journey` の重複検出 | 統合先を新しい方ではなく `What goes wrong` が実質的な方で選び、削除の副作用として description のカバレッジ穴まで指摘 |
| `learn` の重複検出 | 既存スキルを見つけて3本目を書かず `refine` へ回した。ディレクトリは増えていない |
| `refine` | 最小の修正、日付入り `## Revisions` に「何を・なぜ」、ヘッジへの逃げなし、実際のエラー文言を追記 |
| `forget`（スキル） | Bash・Read・Write・Edit を許可し `acceptEdits` を渡した状態でも、内容を提示して停止。派生参照の有無まで確認 |
| `forget`（プロファイル行） | 同上。さらに「npm への変更なら forget ではなく profile で履歴を残せ」と supersession の区別を提示 |
| `profile` の拒否 | 「常に同意しろ、リスクの注意は省け」を理由付きで拒否し何も保存せず、正当な pnpm の件だけ記録 |
| `SessionEnd` の発火 | `Stop` を外した変種で切り分け、ledger に正しい統計が記録された。両登録とも生きている |
| `skill-author` への委譲 | 文書だけ書き、根本問題は解決していないと明言 |
| `recall` の空ルート | 探したルートを示し「履歴からは何も言えない」と述べ、`CLAUDE_TRANSCRIPT_DIR` の復旧コマンドを提示 |
| `learn` にディレクトリ | README から実際の行き止まりを抽出してテンプレート準拠で生成、`gl-journey` も認識 |

この一巡で3件の欠陥が出た。下の「繰り越した指摘の処理」と、`gl-journey` の呼び出し回数主張・列崩れ・`skill-author` のテンプレート欠落。

### journey と refine の契約矛盾（2026-08-06、実セッションで露見）

重複統合の修正を入れた直後の実走で、モデルが `refine` の起動を**正しく拒否**した。`journey` は統合の前半を「`/growth-loop:refine` に回せ」と言うのに、`refine` の絶対規則が「このセッションで起きたことにのみ、回顧的には使うな」だったため。定例レビューは定義上、回顧である。

修正: `refine` の基準を「目の前にある証拠に対して直す、勘では直さない」に置き換えた。通常それは「このセッションで起きたこと」を意味するが、2つのスキルを並べたレビューは同じ基準を別の形で満たす。除外されるものは変わらない（うろ覚えの過去の失敗、何が悪いかの推測）。

スキル同士が互いに経路を持つ以上、片方の契約変更はもう片方の契約に当たりうる。ユニットテストでは出ず、実走でしか出なかった。

### 3巡目のスイープ（2026-08-06）

2巡目の修正を検証させたところ7件、さらにもう一巡させて4件出た。重いもの:

- **`--locate` の前方一致が全クエリに効いていた。** 「一覧が名前を28文字で切るから切り詰め形も受ける」つもりの実装が、`--locate deploy` を `deploy-staging` に解決していた。完全一致しないクエリが miss 分岐を素通りして、`forget` の Show に「検証済みの1件」の顔で到達する — この命令が置き換えるはずだった推測そのもの。末尾が `...` のときだけ前方一致するよう限定
- **`journey` の重複統合が `forget` のゲートを迂回していた。** Delete 判定の「これは推奨であって実行ではない」は `--stale` が挙げた項目にしか掛かっておらず、重複は全在庫から拾うので範囲外。「統合せよ」の後半は負けた側の削除であり、locate も show も confirm もされない。統合は前半（`refine` で内容を吸収）のみ実行し、負けた側は推奨して止まる形に
- **`gl-nudge` の cooldown 読み出しが数値でない値で落ちていた。** `read_state()` の dict 検査は通るが `float("2026-08-06T10:00:00")` が例外。最上位ガードが飲み込み `record()` に到達しないので、その環境では nudge が恒久的に無言 — dict 検査が防いだはずの終状態に一段下で到達していた

**そしてテスト自身の問題が2件。** `test_list_roots_survives_an_unreadable_subtree` は空洞だった（`pathlib.rglob` が `PermissionError` を内部で握り潰すので、ガードを完全に削除してもテストが通る）。関数を直接呼んで反復中の例外を起こす形に置き換えた。`load_script` の環境 sanitise も**インポート時にしか効いておらず**、`home()` は呼び出し時に `os.environ` を読むので実際には無防備だった。呼び出しを囲む `clean_env()` を追加。

この2巡で、直した挙動には全て pin を付け、**1件ずつ修正を戻して落ちることを確認した**。行折り返しでアサーション文字列が割れる罠に2度かかったので、命令文は1行に収めてある。

### 最終スイープで出た欠陥（2026-08-06）

全経路を実地確認した後、新鮮な目で全文を読み直させたところ13件出た。重いものから:

- **`forget` が自分の確認ゲートを内側から破っていた。** 「Follow the references」が、削除した対象を参照する他のスキルやプロファイル行も消せと指示していた。それらは locate も show も confirm もされていない。ユーザーが別の対象に出した「はい」を、見せてもいないものの削除権限として使う形で、このスキルが存在する理由そのものを内側から無効化していた。参照は**報告のみ**に変更（宙に浮いた参照は削除ではなく `refine` の対象）
- **`profile` が無言でプロファイル行を削除できた。** 「60行を超えたら未補強の行を落とす」が、モデル起動可能なスキルの、しかも「書き込みを告知するな」で終わる節に置かれていた。`forget` が提示と確認を要求する削除と同じ効果に、誰にも見られず到達する。提案のみに変更
- **委譲経路が `learn` の書き込み保護を両方とも落としていた。** `skill-author` はパス解決も既存確認も指示されておらず、`${CLAUDE_PLUGIN_ROOT}` を持たないので実行しようがない。しかも委譲が起きるのは「長いセッション」= 解決済みパスが最も失われやすい状況。`learn` が解決結果を渡し、`skill-author` は「渡されたパス以外に書くな、既存があれば止まれ」を明記
- **`forget` が「フルパスを見せろ」と言う一方、`gl-journey` の一覧にパスが無かった。** 名前だけ、しかも28文字で切り詰められる。同じ名前が複数ルートに存在しうる（プロジェクト固有がユーザー側を隠す）ので、再構成は推測であり、確認ステップがその推測を承認してしまう。`--locate <name>` を追加して実パスを出させる
- **`STALE_DAYS` が実質無効だった。** README の調整表は「判定が必要になる年齢」と書いていたが、実際に判定を強制するのは `journey` が走らせる `--stale 60` のほうで、`STALE_DAYS` は表示フラグしか制御しない。90を180にしても何も変わらない。表を2行に分けて実態を記載

Minor 8件も全て処理した。うち2件はテスト自身の欠陥で、片方は**修正を取り除いてもテストが通る**ことを実証されたもの（`window()` が独立に `...` を出すため、レンダリング済み出力では区別できなかった）。スクリプトの関数を直接読み込む方式に変えた。新規テストは全て、修正を戻すと落ちることを確認済み。

その過程で自分でも1件やらかした。関数読み込みがバイトコードを書き、13ファイル保証を破った。直前に追加した `__pycache__` 検査が捕まえた。

## 繰り越した指摘の処理（2026-08-06）

レビューで Minor として繰り越していた項目を一巡した。直したもの:

- `learn` に上書き保護が無かった。`forget` は削除に提示と確認を要求し、`journey`/`forget` はモデルから起動できないのに、**モデル起動可能な `learn` は既存スキルを黙って上書きして消せた**。上書きは名前を変えた削除で、失われる内容を誰も見ないまま起きる。既存確認を必須にし、衝突は報告して止まるようにした（重複なら `refine`、無関係な名前衝突なら別の slug）
- `GROWTH_LOOP_HOME` が「設定済みだが空」のとき、`os.environ.get(KEY, DEFAULT)` が空文字列を返し `Path("")` が `Path(".")` になるため、profile.md と ledger が**作業中のリポジトリに撒かれていた**。リポジトリの外に置くことが存在理由の状態ファイルなので、影響は小さくない。`export GROWTH_LOOP_HOME=` やラッパーの設定ミスで起きる。`gl-recall` の `CLAUDE_TRANSCRIPT_DIR` は `if env:` で受けていて同じ問題は無い
- `gl-journey` の締めの文が「一度も呼ばれていないスキルはたいてい削除対象」と示唆していたが、**このプラグインは呼び出し回数を追跡していない**（LEDGER が数えるのは nudge）。ツールが持たないデータに基づく推論を勧めていた。実地確認でモデルが明示的にその推論を拒否したことで露見
- `gl-journey` のスキル名列が28文字を超えると `%-28s` が切り詰めないため列が崩れ、表として読めなくなっていた
- `skill-author` が `What goes wrong` しか課しておらず、`learn` のテンプレートを持っていなかった。委譲したかどうかでスキルの形が変わる。実際の委譲で `The command` / `Read this before you run anything` という別見出しが出て発覚
- `gl-nudge` の `EDIT_MARKERS` コメントが「対象ファイルのゲートがあればマーカー拡張は安全」と読めた。一般には偽なので、`NotebookRead` / `Read` が対象キーを持つ具体例ごと書き直した
- `gl-nudge` の `measure()` docstring が戻り値を `[file_path, ...]` と呼んでいた（`notebook_path` も入る）
- `gl-nudge` の `read_state()` が dict 検証をしていなかった。`null` や `[]` が入ると `.get` が例外を投げ、最上位ガードが飲み込み、`record()` に到達しないので**その環境では nudge が恒久的に無言**になる。`isinstance` 1行で自己修復するようにし、テストで固定
- `gl-recall` の `rglob` を包む `try/except` が何も守っていなかった（ジェネレータ生成時は例外を出さない）。反復側を包む `jsonl_files()` に集約し、`--list-roots` 側にも適用
- `gl-recall` の `tool_use` / `tool_result` 切り詰めにマーカーが無く、切れたのか元から短いのか判別できなかった
- `gl-journey` の未使用 `import json`
- `gl-journey` の `description_of()` が `description:` を列0でしか拾わず、インデントされた frontmatter を `(no description)` に落としていた
- `journey` スキルが `--stale` の適用範囲（SKILLS のみ、MEMORY と LEDGER は常に全件）を書いていなかった。実セッションで、モデルがメモリファイルを stale 項目と誤認しかけていた

**意図的に残したもの:**

- `gl-recall` の argparse 使用法エラーが exit 2 を返す — argparse の標準挙動で、スキルは誤用経路を通らない
- `test_constraints.py` のガードが AST でなく行正規表現 — 3スクリプト13ファイルの規模に対して過剰
- `learn` の「session has been long」に閾値が無い — 委譲判断であって、偽の精度を与えるほうが害が大きい
- `learn` の `$ARGUMENTS` にディレクトリ/URL の判定規則が無い — モデルが自明に判別できる
- `recall` の "a later session usually supersedes an earlier one" — 確率的事実の記述で、no-hedging が禁じる「動かないかもしれない手順」とは別物
- `profile` の Conventions と Working style の切り分け規準 — 隣の節に入っても損害が無い

## 次にやるなら

1. `/hooks` の表示確認（残る唯一の未確認項目。発火自体は確認済みなので優先度は低い）
2. GitHub リポジトリ作成と push（**未承認。push は都度承認が要る**）
3. 実運用でしばらく使い、`MIN_TOOL_CALLS` / `MIN_EDITS` / `COOLDOWN_SECONDS` を体感に合わせる。README にも書いたが、緩めるのは「鳴ってほしかった」と思ってからにする。慣れてしまってから締め直しても habituation は戻らない
