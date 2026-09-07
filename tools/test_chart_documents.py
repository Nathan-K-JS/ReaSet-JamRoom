"""Behavioral regressions for actual import generation, not a reference copy."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import jamroom_chart as model
import jamroom_import as ji


class ChartTests(unittest.TestCase):
    def test_chord_after_last_word_does_not_jump_to_first_word(self):
        templates=model.parse_chart('[Verse]\n[ch]C[/ch]                    [ch]G[/ch]\nHere we sing')
        doc,_=model.build_document({'duration':20,'lyrics':{'synced':True,'lines':[
            {'time':0,'text':'Here we sing'}]}},templates,[])
        self.assertEqual(doc['sections'][0]['rows'][0]['anchors'][1]['offset'],len('Here we sing'))

    def test_header_repeats_and_lead_break_preserve_the_pattern(self):
        templates=model.parse_chart('[Lead break x2]\n[ch]C[/ch] [ch]G[/ch]')
        doc,_=model.build_document({'duration':30},templates,[])
        self.assertEqual(doc['sections'][0]['label'],'Lead Break')
        self.assertEqual(doc['sections'][0]['repeat'],2)
        self.assertEqual(doc['sections'][0]['progression'],['C','G'])

    def test_plain_lyrics_remain_available_without_invented_timings(self):
        doc,_=model.build_document({'duration':30,'lyrics':{'plain':'First line\nSecond line'}},[],[])
        self.assertEqual(doc['sections'][0]['label'],'Untimed lyrics')
        self.assertEqual(len(doc['sections'][0]['rows']),2)
        self.assertNotIn('start',doc['sections'][0]['rows'][0])

    def job(self):
        return {"duration": 60, "lyrics": {"synced": True, "lines": [
            {"time": 10, "text": "First example line"}, {"time": 12, "text": ""},
            {"time": 30, "text": "Second example line"}, {"time": 34, "text": ""}]}}

    def test_gap_markers_end_items(self):
        self.assertEqual(model.lyric_items(self.job())[0]["end"], 12)

    def test_sections_do_not_interleave_lyric_and_solo_chords(self):
        templates = model.parse_chart('[Intro]\n[ch]Am[/ch] [ch]F[/ch] x2\n\n[Verse]\n[ch]C[/ch]    [ch]G[/ch]\nFirst example line\n\n[Solo]\n[ch]Dm[/ch] [ch]E[/ch]\n\n[Chorus]\n[ch]F[/ch]\nSecond example line')
        doc, events = model.build_document(self.job(), templates, [])
        model.validate_document(doc)
        self.assertEqual([s["label"] for s in doc["sections"]], ['Intro', 'Verse', 'Solo', 'Chorus', 'Instrumental passage'])
        verse = doc["sections"][1]
        self.assertEqual((verse["start"], verse["end"]), (10,12))
        self.assertEqual(doc["sections"][2]["progression"], ['Dm','E'])
        self.assertEqual(events, [], 'Unknown chord timing must not become fabricated events')
        self.assertEqual(verse["rows"][0]["anchors"][1]["symbol"], 'G')

    def test_explicit_repeat_reference_and_pattern_count(self):
        t = model.parse_chart('[Chorus]\n[ch]Am[/ch] [ch]F[/ch] x4\n\n[Chorus]')
        self.assertEqual(t[0]["rows"][0]["repeat"],4)
        self.assertEqual(t[1]["reference"],t[0]["id"])

    def test_abbreviated_chorus_reused_at_later_occurrence(self):
        job=self.job(); job['lyrics']['lines'][2]['text']='First example line'
        doc,_=model.build_document(job,model.parse_chart('[Chorus]\n[ch]C[/ch]\nFirst example line'),[])
        vocals=[s for s in doc['sections'] if s['kind']=='vocal']
        self.assertEqual(len(vocals),2)
        self.assertEqual([s['label'] for s in vocals],['Chorus','Chorus'])
        self.assertNotEqual(vocals[0]['id'],vocals[1]['id'])

    def test_conflicting_identical_lyrics_do_not_choose_arbitrary_harmony(self):
        templates=model.parse_chart('[Verse]\n[ch]C[/ch]\nFirst example line\n[Chorus]\n[ch]F#[/ch]\nFirst example line')
        doc,_=model.build_document(self.job(),templates,[])
        self.assertEqual(doc['sections'][1]['evidence'],'unknown')

    def test_instrumental_song_and_sustained_chord_are_valid(self):
        doc,events=model.build_document({'duration':60},model.parse_chart('[Intro]\n[ch]C[/ch]'),[{'start':0,'end':60,'chord':'C'}])
        model.validate_document(doc)
        self.assertEqual(events,[{'start':0,'end':60,'chord':'C'}])

    def test_rest_is_not_extended_to_next_chord(self):
        detected=[{'start':0,'end':2,'chord':'C'},{'start':8,'end':10,'chord':'G'}]
        _,events=model.build_document({'duration':10},[],detected)
        self.assertEqual(events[0]['end'],2)

    def test_manual_offset_rebuilds_document_and_words_together(self):
        job=self.job();job['lyrics']['offset_override']=2
        doc,_=model.build_document(job,model.parse_chart('[Verse]\n[ch]C[/ch]\nFirst example line'),[])
        verse=next(s for s in doc['sections'] if s['kind']=='vocal')
        self.assertEqual(verse['start'],12)
        self.assertEqual(verse['rows'][0]['end'],14)

    def test_actual_correlation_sign_both_directions(self):
        for offset in (-2,0,2):
            with self.subTest(offset=offset), tempfile.TemporaryDirectory() as td:
                folder=Path(td);(folder/'vocals.wav').touch()
                activity=np.zeros(120)
                for t in (10,40,70): activity[t+offset:t+offset+4]=1
                job={'stems':[{'slot':'LEAD_VOX','file':'vocals.wav'}], 'lyrics':{'synced':True,'lines':[
                    {'time':t,'text':text} for t,text in [(10,'a'),(14,''),(40,'b'),(44,''),(70,'c'),(74,'')]]}}
                with patch.object(ji,'_activity',return_value=(activity,1.)),patch.object(ji,'_vocal_onset',return_value=None),patch.object(ji,'save_job') as save:
                    ji.stage_lyrics_align(job,folder,True,persist=False)
                self.assertEqual(job['lyrics']['align']['shift'],offset)
                save.assert_not_called()

    def test_generator_is_deterministic_and_does_not_change_input(self):
        job=self.job();before=copy.deepcopy(job)
        a,_=model.build_document(job,[],[]);b,_=model.build_document(job,[],[])
        self.assertEqual(a['revision'],b['revision']);self.assertEqual(job,before)

    def test_invalid_duration_rejected(self):
        with self.assertRaises(ValueError):model.build_document({'duration':float('nan')},[],[])


if __name__=='__main__':unittest.main()
