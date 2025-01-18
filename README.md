# SER FFMPEG v0.2-dev

## 概要

SER動画をフレーム指定で切り出して ffmpeg で一般的な動画形式に変換するスクリプトです。SER動画のタイムスタンプからタイムスタンプ表示を追加する機能もあります。

ffmpeg は元々SER動画の入力に対応していますが、フレーム指定の切り出し(trim フィルター)の際に開始フレームが後ろの方にあると頭出しが非常に遅い(おそらく動画を先頭から読み込んでフレームを数えて頭出ししている)ので、SERの固定長フレームの性質を利用して高速に頭出しできるようにしました。

また、RAWで撮影したカラーSER動画の debayer 処理をスクリプト側で行うので ffmpeg でフレームのクロッピング(crop フィルター)を行った際に色がおかしくなる(debayer がバグる？)問題も回避できます。

## 動作環境

以下の環境で動作を確認しています。

- python 3.10.12
  - numpy 2.2.0
  - opencv-python 4.10.0.84
  - pillow 11.0.0
- ffmpeg 4.4.2

venv 環境で `pip install -r requirments.txt` でモジュールをインストールして動作確認しています。

OS は Ubuntu 22.04 で動作を確認しています。Windows, macOS でも動くように作ってありますが確認はしていません。以下の使用例では Linux の bash でのコマンドラインを例示しています。

入力動画は SharpCap 4.1 で撮影した以下のカメラ/モードについて動作を確認しています。

- ASI294MC Pro / 8bit RAW
- ASI290MC / 16bit RAW
- ASI290MM / 16bit RAW

タイムスタンプは SharpCap 等で撮影した際にSER動画内に埋め込まれたフレーム毎のタイムスタンプ値(SharpCap のオプションでフレーム画像にタイムスタンプを描画する機能とは別に常に数値として記録されているものです)を使用しています。

## 使用方法

```
usage: ser-ffmpeg.py [-h] [--speed SPEED] [--ffplay] [--no-timestamp]
                     [--timestamp-only] [--localtime] [--font FONT]
                     [--font-size FONT_SIZE] [--font-color FONT_COLOR]
                     [--timestamp-position TIMESTAMP_POSITION]
                     [--timestamp-margin TIMESTAMP_MARGIN TIMESTAMP_MARGIN]
                     ser_file start end framerate
```

ffmpeg には暗黙のうちに ser-ffmpeg が入力されたSER動画から切り出したフレームが1つ目の入力動画として指定されます。

上で列挙された引数とオプション以外のオプション・引数は全て ffmpeg に渡されるので、`framerate` 以降に適切なオプションと出力ファイル名を指定することでSER動画を ffmpeg で可能な任意の加工を施し、任意の形式に変換して出力することができます。

例:
```
./ser-ffmpeg.py foo.ser 123 456 29.97 -c:v libx264 -crf 17 test-h264.mp4
```

この例では、SER動画 `foo.ser` のフレーム番号123から456までを `29.97`fpsの動画として ffmpeg に入力し、ビデオコーデック libx264 でレート固定係数(Constant Rate Factor) 17 でMP4動画 test-h264.mp4 に出力します。

###  引数

| 引数        | 説明                                              |
|-------------|---------------------------------------------------|
| `ser_file`  | 入力するSER動画を指定します。                     |
| `start`     | 処理対象部分の開始フレーム番号を指定します。      |
| `end`       | 処理対象部分の終了フレーム番号を指定します。      |
| `framerate` | 入力するSER動画の平均フレームレートを指定します。 |

フレーム番号は [https://github.com/cgarry/ser-player](SERPlayer) が表示するものと同じで1から始まる番号です。平均フレームレートも SERPlayer に表示されるものを指定すれば OK です。

### オプション
| オプション                             | 説明                                                                                                                                      | デフォルト値 |
|----------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|--------------|
| `--speed SPEED`                        | ffmpeg に入力する映像を何倍速にするか(何倍速相当でフレームをスキップするか)を指定します。                                                 | `1`          |
| `--ffplay`                             | ffmpeg ではなく ffplay に映像を ffmpeg に入力します。ffmpeg に指定するフィルターの効果の確認等に使います。                                |              |
| `--no-timestamp`                       | タイムスタンプを表示しない映像を ffmpeg に入力します(後述)。                                                                              |              |
| `--timestamp-only`                     | 黒バックにタイムスタンプのみを表示した映像を ffmpeg に入力します(後述)。                                                                  |              |
| `--font FONT`                          | タイムスタンプ表示のフォントを指定します。指定がなければ環境から推定した Courier New フォントを使用します(後述)。                         |              |
| `--font-size FONT_SIZE`                | タイムスタンプ表示のフォントサイズを指定します(単位はピクセル)。                                                                          | `24`         |
| `--font-color FONT_COLOR`              | タイムスタンプ表示の文字色を指定します。HTML/CSSのカラーコードが使えます。                                                                | `#FF8800C0`  |
| `--timestamp-position TEXT_POSITION`   | タイムスタンプの表示位置を `top-left`, `top-middle`, `top-right`, `bottom-left`, `bottom-middle`, `bottom-right` のいずれかで指定します。 | `top-left`   |
| `--timestamp-margin MARGIN_X MARGIN_Y` | タイムスタンプ表示のX方向とY方向のマージンを指定します(単位はピクセル)。                                                                  | `0` `0`      |

### フォントについて

デフォルトでは Windows, Linux(Ubuntu 等のディストリビューション), macOS がシステムに標準で持つ Courier New フォントを使用します。他の OS では明示的に `--font FONT` オプションを指定しないとエラーになります。`FONT` に指定するのは TrueType フォントのフォントファイル名です。詳細は[Pillow の ImageFont の説明](https://pillow.readthedocs.io/en/stable/reference/ImageFont.html)を参照してください。

## ライセンス

MITライセンスです。

## 参考: タイムスタンプと映像の分離処理

`--timestamp-only` オプションと `--no-timestamp` オプションでタイムスタンプのみの動画とタイムスタンプなしの動画を作成し、それらを合成することで、タイムスタンプの色調を変えずに元の映像のみに適切なフィルター処理を適用した動画を作成することができます。

例:
```
# タイムスタンプなし動画の作成。ノイズ低減、明度UP、低圧縮の H264 動画。
./ser-ffmpeg.py --no-timestamp 18_05_00.ser 22870 31855 30 -vf 'hqdn3d,eq=gamma=3.13:contrast=1.1155:brightness=-0.01535' -c:v libx264 -crf 18 -pix_fmt yuv444p 2024-12-8-18_05_00-22870_31855-no-timestamp.mp4
# タイムスタンプのみ動画(アルファチャンネル付き)の作成。低圧縮の vp9/webm 動画。
./ser-ffmpeg.py --timestamp-only 18_05_00.ser 22870 31855 30 -c:v vp9 -crf 18 2024-12-8-18_05_00-22870_31855-timestamp-only.webm
# タイムスタンプなし動画とタイムスタンプなし動画をアルファブレンディングで合成。
ffmpeg -i 2024-12-8-18_05_00-22870_31855-no-timestamp.mp4 -c:v libvpx-vp9 -i 2024-12-8-18_05_00-22870_31855-timestamp-only.webm -filter_complex "[0][1]overlay" -c:v libx264 -b:v 10M -pix_fmt yuv420p 2024-12-8-18_05_00-22870_31855-with-timestamp.mp4
```

タイムスタンプのみ動画を作成する際は ffmpeg のオプションに `-c:v vp9` を、出力ファイル名の拡張子に .webm を指定してアルファチャンネル対応の動画形式で出力します。

ffmpeg でタイムスタンプのみ動画とタイムスタンプなし動画を合成する際には `-c libvpx-vp9` オプションをタイムスタンプのみの動画(.webm 形式)を指定する `-i` オプションの直前に指定します。これを指定しないとアルファチャンネルが正しく処理されません。

## 更新履歴

- v0.2: モノクロ動画対応
  - モノクロカメラで撮影した RAW 動画(color_id = 0)の入力に対応
- v0.1: 最初のリリース
