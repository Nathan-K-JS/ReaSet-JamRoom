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
    def test_merged_lyric_lines_do_not_erase_authored_changes(self):
        source='[Pre-Chorus]\n[ch]E[/ch]   [ch]F#m[/ch]\n        Touch the sky\n[ch]E[/ch]   [ch]F#m[/ch]\n        Touch the sea\n[Chorus]\n[ch]C[/ch]          [ch]G[/ch]\nKeep the light on\n[Post-Chorus]\n[ch]Am[/ch]\nLa la la'
        templates=chart.parse_chart(source)
        job={'duration':60,'lyrics':{'synced':True,'lines':[{'time':10,'text':'Touch the sky, touch the sea'}, {'time':20,'text':'Keep the light on'}, {'time':30,'text':'La la la'}]}}
        doc,_=chart.build_document(job,templates,[])
        self.assertEqual([s['label'] for s in doc['sections']],['Pre-Chorus','Chorus','Post-Chorus'])
        self.assertEqual(len(doc['sections'][0]['rows']),2)
        for expected,actual in zip(templates,doc['sections']):
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
        self.assertEqual(doc['sections'][0]['rows'][0]['text'],'     Original words')

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
