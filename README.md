# SL Chat Translator

Second Life（Firestormビューア等）でのチャット用翻訳ツールです。  
DeepL API を使用し、日本語を英語・フランス語・スペイン語に翻訳します。

## 特徴

- **常に最前面表示**: Firestorm の上に重ねて使えます
- **ショートカットキー**: Enter で翻訳、Shift+Enter で改行
- **チャットリアルタイム翻訳**: 指定したチャットログ（オープン、グループ、個人など）から選択し、リアルタイムに翻訳表示
- **クリップボード連携**: 翻訳結果をワンクリックでコピー（翻訳した時点でコピー済なのでそのまま任意のチャット欄にペースト可能）
- **コンパクト**: 400×320 の小さなウィンドウ、マウスでサイズ変更可。また、手動翻訳（上段）とチャットログ監視（下段）は▼で閉じることが可能

## セットアップ

### 1. 必要なライブラリをインストール

```bash
pip install -r requirements.txt
```

### 2. DeepL APIキーを設定

`config.json` を開き、`YOUR_DEEPL_API_KEY_HERE` を実際の APIキーに置き換えてください。

```json
{
    "api_key": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:xx",
    "default_target_lang": "EN"
}
```

APIキーは [DeepL公式サイト](https://www.deepl.com/pro-api) で取得できます（無料版あり）。

### 3. 起動

```bash
python main.py
```

## 使い方

1. **入力欄**に日本語を入力
2. **翻訳先**をプルダウンで選択（EN / FR / ES）
3. **Enterキー**または**「翻訳」ボタン**で翻訳
4. **「クリップボードにコピー」**ボタンでコピー
5. Firestorm のチャット欄に **Ctrl+V** でペースト

## ファイル構成

```
sl-translator/
├── main.py           # アプリケーション本体
├── config.json       # APIキー設定ファイル
├── requirements.txt  # 依存ライブラリ一覧
└── README.md         # このファイル
```

## 注意事項

- `config.json` は他人に共有しないでください（APIキーが含まれます）。
- DeepL 無料版の場合、月間の翻訳文字数に制限があります。
