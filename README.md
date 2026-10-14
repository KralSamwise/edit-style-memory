# Edit Style Memory

**Stop giving your editor the same correction on every project.** Measure references, then remember only the preferences you actually approved, in the right project and format.

```sh
python3 scripts/style_memory.py profile examples/references.json
python3 scripts/style_memory.py learn /tmp/edit-preferences.json examples/approved-feedback.json
python3 scripts/style_memory.py resolve /tmp/edit-preferences.json --project demo-brand --format talking-head-vertical
python3 -m unittest discover -s tests -v
```

The synthetic reference fixture returns a median shot length of 5 seconds across three references. The example feedback resolves caption Y 0.78 and a five-word caption limit. A different project gets no preferences.

To measure your own local footage:

```sh
python3 scripts/style_memory.py measure reference.mp4 --format talking-head-vertical > observation.json
```

Inspect/correct the observation before marking it reviewed and combining at least three references. Requires ffmpeg/ffprobe for video measurement; other commands use only Python's standard library.

This release does not edit video, recognize creators, infer fonts, or predict reach. Cuts and silences detected by thresholds need human/agent visual review. A profile is descriptive evidence; approved feedback is an explicit preference. Your editing agent consumes the resolved values.

## Install as a skill

Clone this repository into your agent's skills directory under the repository name, or ask your agent to read the root `SKILL.md` directly. This is an agent instruction package plus local scripts, not a hosted service. Review scripts before running them. Do not copy credentials or private footage into a public fork.

No metered model API is required by these scripts. Your coding agent and optional rendering tools have their own requirements. Tested locally on macOS; Windows/Linux have not yet been verified.
