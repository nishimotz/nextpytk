# PyPI Trusted Publishing 設定手順（nextpytk）

GitHub Actions から PyPI へTrusted Publishingでリリースする設定。

## 前提

- PyPI プロジェクト: https://pypi.org/project/nextpytk
- リポジトリ: `nishimotz/nextpytk`
- 発行元: GitHub Actions workflow `.github/workflows/publish.yml`

## PyPI 側の設定

1. https://pypi.org/manage/project/nextpytk/settings/publishing/ を開く
2. 「Add a new pending publisher」で以下を入力:
   - **Publisher**: GitHub Actions
   - **Repository owner**: `nishimotz`
   - **Repository name**: `nextpytk`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
3. 「Add」を押す

## リリース手順

```bash
# nextpytk リポジトリの main ブランチでタグを打つ
git checkout main
git pull origin main
git tag -a v0.3.1 -m "Release nextpytk 0.3.1"
git push origin v0.3.1
```

タグを push すると `.github/workflows/publish.yml` が動作し、PyPI に 0.3.1 が公開される。

## ワークフロー概要

- `build` job: uv build で wheel + sdist を作成
- `publish` job: `uv publish --trusted-publishing` を実行
  - `environment: pypi` を指定して OIDC トークンを取得
  - permissions: `id-token: write` が必要

## トラブルシューティング

- `uv publish` が認証エラーになる場合:
  - PyPI の pending publisher が正しく `publish.yml` + environment `pypi` で登録されているか確認
  - GitHub Actions の「Environments」に `pypi` environment が存在し、protection rules が誤ってトリガーをブロックしていないか確認
- タグ push 以外で publish workflow を手動実行する場合:
  - `workflow_dispatch` でもトリガー可能だが、Trusted Publishing は通常タグ push 用に設定
