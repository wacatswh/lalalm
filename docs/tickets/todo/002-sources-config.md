# 002 — `sources.yaml` config with variety + register

**Phase:** P0 · **Depends-on:** — · **Gate:** none

## Goal
Replace hardcoded source lists with one tracked config file that every scraper reads.

## Why
`DEFAULT_SUBS` is a hardcoded list in one scraper. With three scrapers and two language
varieties to keep balanced, "am I collecting enough Manglish?" needs to be a query over
config, not a guess. This is the file that will be edited most often, so it should be data,
not code.

## Scope
Create `sources.yaml` at repo root:
```yaml
sources:
  - kind: reddit          # reddit | youtube | lowyat
    name: singapore
    variety: sg           # sg | my
    register: social      # forum | spoken | social
    enabled: true
  - kind: reddit
    name: Bolehland
    variety: my
    register: social
  - kind: youtube
    name: <channel-id-or-playlist>
    variety: my
    register: spoken
```
Seed it with: `r/singapore`, `r/SingaporeRaw`, `r/malaysia`, `r/Bolehland`, `r/malaysians`,
`r/MalaysianFood`, a Lowyat.NET board list, and a hand-curated set of Malaysian and Singaporean
YouTube channels/podcasts for spoken register. Drop `r/asianamerican` from the current default
list — it is neither variety.

Add a small `scripts/sources.py` loader used by all scrapers. `pyyaml` → `requirements.txt`.

## Done-when
```sh
python3 -c "from scripts.sources import load; s=load(); \
assert s, 'no sources'; \
assert all(x['variety'] in ('sg','my') for x in s), 'bad variety'; \
assert all(x['register'] in ('forum','spoken','social') for x in s), 'bad register'; \
assert {x['variety'] for x in s}=={'sg','my'}, 'need both varieties'; print(len(s),'sources ok')"
```

## Files
`sources.yaml`, `scripts/sources.py`, `requirements.txt`
