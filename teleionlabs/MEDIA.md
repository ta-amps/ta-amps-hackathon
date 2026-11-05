# Media files

Video and voice files are not kept in git. The site serves them from these addresses. A deploy needs copies of them in the same paths under `static/`.

| File | Address | Bytes | sha256 |
| --- | --- | --- | --- |
| `video-gallery/3d-simple/voice.mp3` | https://teleionlabs.com/video-gallery/3d-simple/voice.mp3 | 2160620 | `c823ab811469cba230920973b7eecbdad97b306603f5ab1dbae0d07a622527d3` |
| `media/main-film-20261104o.mp4` | https://teleionlabs.com/media/main-film-20261104o.mp4 | 9147298 | `315eacbcaabe60f3b022ad2b2599d15889f1594b5f9061bb06d4c04f7886cf7d` |

## Word list

Our full banned-word list is kept private. In a public copy, `make check` runs on the made-up sample in `tests/sample-word-list.json` and says so. A deploy can't: the build command in `wrangler.jsonc` drops that setting and fails without the real list.
