# Media files

Video and voice files are not kept in git. The site serves them from these addresses. A deploy needs copies of them in the same paths under `static/`.

| File | Address | Bytes | sha256 |
| --- | --- | --- | --- |
| `media/intelligence-explained-20261103.mp4` | https://teleionlabs.com/media/intelligence-explained-20261103.mp4 | 4673754 | `b605934265d2c26ac8a4a06065a0ab46d1d4cd84af63a8b4a4d6284e1be0d262` |
| `media/omninode-explained-20261103.mp4` | https://teleionlabs.com/media/omninode-explained-20261103.mp4 | 5108762 | `9db10961ad6ad623ab9d438b3432a7f9520bf1e20b36894097e4b3b0ebd12f1f` |
| `media/shim-explained-20261103.mp4` | https://teleionlabs.com/media/shim-explained-20261103.mp4 | 3298733 | `4d498f20e9f287e36a8972cd02ac0b3c436a886481629fb3b701e2254f4d8b10` |
| `video-gallery/3d-simple/voice.mp3` | https://teleionlabs.com/video-gallery/3d-simple/voice.mp3 | 2160620 | `c823ab811469cba230920973b7eecbdad97b306603f5ab1dbae0d07a622527d3` |
| `media/main-film-20261104m.mp4` | https://teleionlabs.com/media/main-film-20261104m.mp4 | 9473423 | `d943000c0cbc3ba7724b7d286fe9c020a0b29c66bafb00f16fcba546a39f70d5` |

## Word list

Our full banned-word list is kept private. In a public copy, `make check` runs on the made-up sample in `tests/sample-word-list.json` and says so. A deploy can't: the build command in `wrangler.jsonc` drops that setting and fails without the real list.
