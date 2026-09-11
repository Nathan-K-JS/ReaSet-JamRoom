"""Musical-content and edit invariants; authored columns survive bad timing."""
import copy
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
from lupa import LuaRuntime
import jamroom_chart as chart
import jamroom_import as importer

ROOT=Path(__file__).resolve().parent.parent

class JobPersistenceTests(unittest.TestCase):
    def test_transient_windows_lock_retries_atomic_replace(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)
            importer.save_job(target,{'old':True})
            replace=Path.replace
            calls=[]
            def locked(path,destination):
                calls.append(path)
                if len(calls)==1:raise PermissionError('Busy reader')
                return replace(path,destination)
            with patch.object(Path,'replace',locked),patch.object(importer.time,'sleep'):
                importer.save_job(target,{'new':True})
            self.assertEqual(json.loads((target/'job.json').read_text()),{'new':True})
            self.assertEqual(len(calls),2)

    def test_persistent_lock_preserves_previous_job(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder);importer.save_job(target,{'old':True})
            with patch.object(Path,'replace',side_effect=PermissionError('Locked')) as replace,patch.object(importer.time,'sleep'):
                with self.assertRaises(PermissionError):importer.save_job(target,{'new':True})
            self.assertEqual(replace.call_count,6)
            self.assertEqual(json.loads((target/'job.json').read_text()),{'old':True})

class SourceChartTests(unittest.TestCase):
    def test_missing_intro_and_explicit_gaps_are_visible_without_invented_chords(self):
        templates=chart.parse_chart('[Verse]\n[ch]C[/ch]\nThe first original line\n[ch]G[/ch]\nThe second original line')
        job={'duration':50,'lyrics':{'synced':True,'lines':[
            {'time':10,'text':'The first original line'},{'time':20,'text':''},
            {'time':30,'text':'The second original line'},{'time':40,'text':''}]}}
        doc,_=chart.build_document(job,templates,[])
        gaps=[s for s in doc['sections'] if s.get('missing_source_chords')]
        self.assertEqual([(s['start'],s['end']) for s in gaps],[(0,10),(20,30),(40,50)])
        self.assertTrue(all(not s['rows'] and not s['progression'] for s in gaps))
        self.assertEqual([r['id'] for s in doc['sections'] for r in s['rows']],['source-0-0','source-0-1'])
        chart.validate_document(doc)

    def test_vocal_interlude_is_not_renamed_after_matching_an_outro(self):
        passage='[ch]C[/ch]\nThese are the original words\n[ch]G[/ch]\nAnd these words repeat again'
        templates=chart.parse_chart('[Interlude]\n'+passage+'\n[Outro]\n'+passage)
        sections,_=chart.source_sections(templates)
        self.assertEqual([s['label'] for s in sections],['Interlude','Outro'])

    def test_common_tail_cannot_supply_a_cue_for_an_unmatched_line(self):
        doc,_=chart.build_document({'duration':30,'lyrics':{'synced':True,'lines':[{'time':10,'text':'We met my dear friend'}]}},
            chart.parse_chart('[Verse]\n[ch]C[/ch]\nWelcome home my dear friend'),[])
        self.assertNotIn('cue',next(r for s in doc['sections'] for r in s['rows']))
        self.assertTrue(any(i['code']=='unlocated_rows' for i in doc['review']['issues']))

    def test_leading_instrumental_uses_explicit_vocal_gap_before_words(self):
        source='[Chorus]\n[ch]C[/ch]\nWe sing together now\n[Bridge] - no chords\nN.C. x2\n\nN.C.\nHere we go again'
        job={'duration':60,'lyrics':{'synced':True,'lines':[{'time':10,'text':'We sing together now'}, {'time':20,'text':''}, {'time':30,'text':'Here we go again'}]}}
        doc,_=chart.build_document(job,chart.parse_chart(source),[])
        bridge=next(s for s in doc['sections'] if any(r['id']=='source-1-0' for r in s['rows']))
        self.assertEqual(bridge['start'],20)
        self.assertEqual(next(r for s in doc['sections'] for r in s['rows'] if r['text'].strip()=='Here we go again')['cue'],30)
        self.assertEqual(bridge['confidence'],'estimated')

    def test_global_word_alignment_keeps_later_repetitions_after_unique_bridge(self):
        source=('unique bridge here '+'a b c d e f '*4+'final ending now').split()
        sung=source[:]
        sung[8]='different';sung[18]='wording'
        runs=chart.matching_word_runs(source,sung)
        pairs={a+k:b+k for a,b,size in runs for k in range(size)}
        self.assertEqual(pairs,{i:i for i in range(len(source)) if i not in (8,18)})

    def test_bracketed_heading_with_instruction_is_not_sung_text(self):
        for suffix in (' - no chords', ' (quietly)', ': repeat twice', ' \u2014 drums only'):
            with self.subTest(suffix=suffix):
                source='[Verse 1]\n[ch]C[/ch]\nHere we sing\n[Bridge]'+suffix+'\nN.C.\nAnother line to sing\n[Chorus]\n[ch]G[/ch]\nThere we go'
                sections=chart.parse_chart(source)
                self.assertEqual([s['label'] for s in sections],['Verse 1','Bridge','Chorus'])
                self.assertEqual(sections[1]['rows'][0]['text'],'Another line to sing')
                self.assertEqual(sections[1]['rows'][0]['anchors'][0]['symbol'],'N.C.')
                self.assertTrue(sections[1]['instruction'])
                self.assertFalse(any('[Bridge]' in r['text'] for s in sections for r in s['rows']))

    def test_mislabeled_repeated_passage_keeps_every_source_column(self):
        chorus='[ch]C[/ch]   [ch]G[/ch]\nWe are singing in the rain\n[ch]Am[/ch]\nEvery little light will shine'
        templates=chart.parse_chart('[Chorus]\n'+chorus+'\n[Instrumental]\n[ch]F[/ch]\n\n'+chorus)
        before=copy.deepcopy(templates)
        doc,_=chart.build_document({'duration':60},templates,[])
        self.assertEqual([s['label'] for s in doc['sections']],['Chorus','Instrumental','Chorus'])
        fields=lambda sections:[(r['id'],r['text'],r['anchors']) for s in sections for r in s['rows']]
        self.assertEqual(fields(templates),fields(doc['sections']))
        self.assertEqual(templates,before)
        self.assertEqual(doc['review']['status'],'needs_review')

    def test_unknown_vocals_are_not_arbitrarily_named_chorus(self):
        templates=chart.parse_chart('[Solo]\n[ch]C[/ch]\nThese are some entirely new words\n[ch]G[/ch]\nWith another line to sing')
        doc,_=chart.build_document({'duration':30},templates,[])
        self.assertEqual(doc['sections'][0]['label'],'Vocal section')

    def test_zero_instrumental_gap_does_not_make_a_flashing_page(self):
        templates=chart.parse_chart('[Verse]\n[ch]C[/ch]\nHere we are now\n[Instrumental]\n[ch]D[/ch]\n[Chorus]\n[ch]G[/ch]\nThere we go again')
        job={'duration':40,'lyrics':{'synced':True,'lines':[{'time':5,'text':'Here we are now'},{'time':15,'text':'There we go again'}]}}
        doc,_=chart.build_document(job,templates,[])
        self.assertEqual(len(doc['sections']),3)
        self.assertEqual([r['id'] for s in doc['sections'] for r in s['rows']],['source-0-0','source-1-0','source-2-0'])
        self.assertEqual(doc['sections'][-1]['start'],15)
        self.assertTrue(any(i['code']=='unresolved_instrumental_boundary' for i in doc['review']['issues']))
        self.assertEqual(doc['alignment']['matched_rows'],2)
        self.assertEqual(doc['review']['status'],'needs_review','Perfect text match is not musical verification')

    def test_missing_recording_passage_is_flagged_even_if_all_chart_words_match(self):
        templates=chart.parse_chart('[Verse]\n[ch]C[/ch]\nHere we are now')
        job={'duration':40,'lyrics':{'synced':True,'lines':[{'time':5,'text':'Here we are now'},{'time':15,'text':'Entirely different missing passage after the verse'}]}}
        doc,_=chart.build_document(job,templates,[])
        self.assertTrue(any(i['code']=='unrepresented_recording_words' for i in doc['review']['issues']))

    def test_merged_lyric_lines_do_not_erase_authored_changes(self):
        source='[Pre-Chorus]\n[ch]E[/ch]   [ch]F#m[/ch]\n        Touch the sky\n[ch]E[/ch]   [ch]F#m[/ch]\n        Touch the sea\n[Chorus]\n[ch]C[/ch]          [ch]G[/ch]\nKeep the light on\n[Post-Chorus]\n[ch]Am[/ch]\nLa la la'
        templates=chart.parse_chart(source)
        job={'duration':60,'lyrics':{'synced':True,'lines':[{'time':10,'text':'Touch the sky, touch the sea'}, {'time':20,'text':'Keep the light on'}, {'time':30,'text':'La la la'}]}}
        doc,_=chart.build_document(job,templates,[])
        self.assertEqual([s['label'] for s in doc['sections']],['Intro','Pre-Chorus','Chorus','Post-Chorus'])
        self.assertEqual(len(doc['sections'][1]['rows']),2)
        for expected,actual in zip(templates,doc['sections'][1:]):
            for a,b in zip(expected['rows'],actual['rows']):
                self.assertEqual(a['text'],b['text'])
                self.assertEqual(a['anchors'],b['anchors'])

    def test_tab_riff_is_not_a_lyric_and_repeat_does_not_expand(self):
        source='[Intro]\n[ch]F#m[/ch]  [ch]B[/ch]\ne|-------|\nB|-------|\nD|---2---| x2\n   \u2193 \u2191\n[Verse]\n[ch]C[/ch]\nSome words\n[Outro]\n[ch]C[/ch] [ch]G[/ch] x4, [ch]E[/ch]'
        templates=chart.parse_chart(source)
        self.assertEqual(templates[0]['kind'],'instrumental')
        self.assertEqual(templates[0]['rows'][0]['repeat'],2)
        self.assertEqual(templates[-1]['rows'][0]['repeat_at'],2)
        doc,_=chart.build_document({'duration':60},templates,[])
        self.assertEqual(doc['sections'][-1]['label'],'Outro')
        self.assertEqual(len(doc['sections'][-1]['rows'][0]['anchors']),3)

    def test_no_chord_and_source_whitespace_survive(self):
        templates=chart.parse_chart('[Verse]\n[ch]F#m[/ch]  N.C.                [ch]E[/ch]\n     Original words')
        self.assertEqual([a['symbol'] for a in templates[0]['rows'][0]['anchors']],['F#m','N.C.','E'])
        doc,_=chart.build_document({'duration':30,'lyrics':{'synced':True,'lines':[{'time':5,'text':'Different words entirely'}]}},templates,[])
        self.assertEqual(next(r for s in doc['sections'] for r in s['rows'])['text'],'     Original words')

class ChartEditTests(unittest.TestCase):
    def setUp(self):
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute('J=dofile('+json.dumps((ROOT/'Requirements/ReaSet_JSON.lua').as_posix())+'); E=dofile('+json.dumps((ROOT/'Requirements/ReaSet_ChartEdit.lua').as_posix())+')')
        self.doc,_=chart.build_document({'duration':60,'lyrics':{'synced':True,'lines':[{'time':5,'text':'Here we sing'},{'time':30,'text':'There we go'}]}},chart.parse_chart('[Intro]\n[ch]C[/ch]\n[Verse]\n[ch]G[/ch]                  [ch]F[/ch]\nHere we sing\n[ch]Am[/ch]\nThere we go'),[])

    def edit(self,action,data):
        self.lua.globals().blob=json.dumps(self.doc);self.lua.globals().payload=json.dumps(data)
        self.lua.globals().action=action
        return json.loads(self.lua.eval('J.encode(E.apply(J.decode(blob),action,J.decode(payload),60))'))

    def test_cue_changes_no_row_or_chord_data(self):
        result=self.edit('cue',{'section':2,'time':8})
        self.assertEqual(result['sections'][1]['start'],8)
        self.assertEqual(result['sections'][0]['end'],8)
        self.assertEqual(result['sections'][1]['rows'],self.doc['sections'][1]['rows'])

    def test_whole_song_offset_is_reversible_and_preserves_every_cue(self):
        original=copy.deepcopy(self.doc)
        self.doc=self.edit('offset',{'seconds':-2.5})
        self.assertEqual(self.doc['sections'],original['sections'])
        self.assertEqual(self.doc['timing_offset'],-2.5)
        self.doc=self.edit('offset',{'seconds':1.25})
        self.doc=self.edit('offset',{'seconds':0})
        self.assertEqual(self.doc['sections'],original['sections'])
        with self.assertRaises(Exception):self.edit('offset',{'seconds':60})

    def test_split_and_join_preserve_every_source_row(self):
        rows=[r for s in self.doc['sections'] for r in s['rows']]
        groups=[{'label':'Opening','start':0,'rows':[rows[0]['id']]},{'label':'Verse','start':5,'rows':[rows[1]['id']]},{'label':'Chorus','start':30,'rows':[rows[2]['id']]}]
        result=self.edit('layout',{'sections':groups})
        self.assertEqual([r for s in result['sections'] for r in s['rows']],rows)
        self.doc=result
        joined=self.edit('layout',{'sections':[{'label':'Whole song','start':0,'rows':[r['id'] for r in rows]}]})
        self.assertEqual(joined['sections'][0]['rows'],rows)

    def test_drop_reorder_duplicate_or_crossed_cues_rejected(self):
        rows=[r['id'] for s in self.doc['sections'] for r in s['rows']]
        for ids in [rows[:-1],list(reversed(rows)),rows+rows[:1]]:
            with self.assertRaises(Exception):self.edit('layout',{'sections':[{'label':'Song','start':0,'rows':ids}]})
        with self.assertRaises(Exception):self.edit('cue',{'section':2,'time':61})

    def test_page_cue_preserves_authored_columns(self):
        row=self.doc['sections'][1]['rows'][0]
        result=self.edit('pagecue',{'section':2,'time':10,'row':row['id'],'column':0})
        self.assertEqual(result['sections'][1]['rows'][0]['anchors'],row['anchors'])
        self.assertEqual(result['sections'][1]['rows'][0]['page_cues'],{'0':10})

if __name__=='__main__':unittest.main()
