#!/usr/bin/env python3
"""Local editing measurements and explicit, scope-bound review preferences."""
import argparse
import copy
import hashlib
import json
import math
import re
import statistics
import subprocess
from pathlib import Path

FIELDS = {'caption_y': (0, 1), 'caption_max_words': (1, 20), 'pause_keep_sec': (0, 5), 'zoom_max': (1, 2)}

def number(v, low=0, high=float('inf')):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not low <= v <= high:
        raise ValueError(f'Expected finite number between {low} and {high}')
    return v

def scope(value):
    if not isinstance(value, dict) or set(value) != {'project', 'format'} or any(not isinstance(x, str) or not x.strip() for x in value.values()):
        raise ValueError('Scope requires nonempty project and format strings')
    return value

def measure(video, format_name, threshold=.3):
    number(threshold, .01, 1)
    video = Path(video)
    def run(args):
        p = subprocess.run(args, capture_output=True, text=True)
        if p.returncode: raise ValueError(p.stderr[-1500:])
        return p
    probe = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(video)]).stdout)
    seconds = number(float(probe['format']['duration']), .001)
    scan = run(['ffmpeg', '-hide_banner', '-i', str(video), '-an', '-vf', f"select='gt(scene,{threshold})',showinfo", '-f', 'null', '-'])
    cuts = sorted(set(float(x) for x in re.findall(r'pts_time:([0-9.]+)', scan.stderr) if 0 < float(x) < seconds))
    pauses = []
    if any(s['codec_type'] == 'audio' for s in probe['streams']):
        audio = run(['ffmpeg', '-hide_banner', '-i', str(video), '-vn', '-af', 'silencedetect=noise=-35dB:d=0.2', '-f', 'null', '-'])
        pauses = [float(x) for x in re.findall(r'silence_duration: ([0-9.]+)', audio.stderr)]
    digest = hashlib.sha256()
    with video.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): digest.update(chunk)
    return {'id':video.name, 'source_sha256':digest.hexdigest(), 'format':format_name, 'duration_sec':seconds,
            'cut_times_sec':cuts, 'pause_durations_sec':pauses, 'reviewed':False,
            'measurement':{'method':'ffmpeg-scene-and-silence', 'scene_threshold':threshold, 'silence_db':-35, 'silence_min_sec':.2},
            'limitations':['Scene changes are candidates, not verified editorial cuts.', 'Silence is not necessarily a speech pause. Inspect and set reviewed=true only after checking.']}

def profile(refs):
    if len(refs) < 3: raise ValueError('At least three reviewed references are required')
    formats = {r['format'] for r in refs}
    if len(formats) != 1: raise ValueError('Do not mix formats in one profile')
    identities = [r.get('source_sha256') or r.get('source_url') or r.get('id') for r in refs]
    if any(not x for x in identities) or len(set(identities)) != len(refs): raise ValueError('References need distinct source identities')
    metrics = {'shot_median_sec':[], 'cuts_per_minute':[], 'pause_median_sec':[], 'caption_y':[]}
    for r in refs:
        if r.get('reviewed') is not True: raise ValueError('Check automatic measurements before profiling')
        d = number(r['duration_sec'], .001)
        cuts = [number(x, 0, d) for x in r['cut_times_sec']]
        if cuts != sorted(set(cuts)) or any(x == 0 or x == d for x in cuts): raise ValueError('Cuts must be unique, ordered and strictly inside duration')
        edges = [0] + cuts + [d]
        metrics['shot_median_sec'].append(statistics.median(b-a for a,b in zip(edges,edges[1:])))
        metrics['cuts_per_minute'].append(len(cuts)*60/d)
        pauses = [number(x, .001, d) for x in r.get('pause_durations_sec', [])]
        if pauses: metrics['pause_median_sec'].append(statistics.median(pauses))
        if 'caption_y' in r: metrics['caption_y'].append(number(r['caption_y'],0,1))
    summaries = {k:{'median':statistics.median(v), 'min':min(v), 'max':max(v), 'reference_count':len(v)} for k,v in metrics.items() if v}
    return {'schema_version':1,'format':next(iter(formats)), 'reference_count':len(refs), 'source_ids':identities,
            'metrics':summaries, 'status':'observations-only',
            'limitations':['Describes this sample; does not prove causes of engagement.', 'Not a creator clone. No identity, assets, or automatic cut settings are copied.']}

def learn(store, event):
    scope(event['scope'])
    if event.get('approved') is not True: raise ValueError('Only explicit approved preferences may be saved')
    if not isinstance(event.get('id'),str) or not event['id'].strip() or not isinstance(event.get('evidence'),str) or not event['evidence'].strip():
        raise ValueError('Preference needs a stable id and review evidence')
    if not event.get('values') or any(k not in FIELDS for k in event['values']): raise ValueError('Unknown or empty preference fields')
    for k,v in event['values'].items():
        number(v,*FIELDS[k])
        if k == 'caption_max_words' and int(v) != v: raise ValueError('caption_max_words must be an integer')
    events = copy.deepcopy(store.get('events', []))
    for old in events:
        if old['id'] == event['id']:
            if old != event: raise ValueError('Conflicting event id; use a new id for a correction')
            return store
    events.append(copy.deepcopy(event))
    return {'schema_version':1,'events':events}

def resolve(store, wanted):
    scope(wanted)
    values, evidence = {}, {}
    for event in store.get('events',[]):
        # Validate on the read path as well; no trusting hand-edited store files.
        learn({'events':[]},event)
        if event['scope'] == wanted:
            values.update(event['values'])
            evidence.update({k:event['id'] for k in event['values']})
    return {'schema_version':1, 'scope':wanted, 'values':values, 'evidence_ids':evidence,
            'precedence':'Current user request overrides these preferences. Review before applying.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    m=sub.add_parser('measure');m.add_argument('video');m.add_argument('--format',required=True);m.add_argument('--threshold',type=float,default=.3)
    a=sub.add_parser('profile');a.add_argument('references')
    a=sub.add_parser('learn');a.add_argument('store');a.add_argument('event')
    a=sub.add_parser('resolve');a.add_argument('store');a.add_argument('--project',required=True);a.add_argument('--format',required=True)
    args=p.parse_args()
    read=lambda path: json.loads(Path(path).read_text())
    try:
        if args.command=='measure': result=measure(args.video,args.format,args.threshold)
        elif args.command=='profile': result=profile(read(args.references))
        elif args.command=='resolve': result=resolve(read(args.store),{'project':args.project,'format':args.format})
        else:
            result=learn(read(args.store) if Path(args.store).exists() else {},read(args.event))
            dest=Path(args.store);temp=dest.with_name(dest.name+'.tmp');temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(dest)
        print(json.dumps(result,indent=2))
    except (ValueError,KeyError,TypeError,OSError) as e: p.exit(2,f'Error: {e}\n')
if __name__=='__main__': main()
