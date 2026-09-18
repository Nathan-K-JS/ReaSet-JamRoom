import copy
import math
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
from unittest.mock import patch
import wave

from lupa import LuaRuntime
import jamroom_loudness as level

ROOT = Path(__file__).resolve().parent.parent


class LoudnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def tone(self, name, amplitude):
        with wave.open(str(self.folder / name), 'wb') as out:
            out.setnchannels(2); out.setsampwidth(2); out.setframerate(48000)
            out.writeframes(b''.join(struct.pack('<hh', *([int(amplitude * 32767 * math.sin(2 * math.pi * 997 * n / 48000))] * 2)) for n in range(96000)))

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
    def test_real_measurement_matches_loud_and_quiet_mix_and_excludes_click(self):
        self.tone('loud.wav', .7); self.tone('quiet.wav', .35)
        self.tone('click.wav', .99)
        reports = []
        for name in ('loud.wav', 'quiet.wav'):
            job = {'slots':[{'slot':'BASS','file':name}, {'slot':'CLICK','file':'click.wav'}]}
            report = level.analyse(job, self.folder)
            self.assertEqual(report['status'], 'measured')
            self.assertAlmostEqual(report['predicted_lufs'], -23, places=4)
            self.assertLessEqual(report['peak_dbtp'] + report['gain_db'], -3)
            reports.append(report)
            with patch.object(level, 'scan', side_effect=AssertionError('Repeated analysis')):
                self.assertEqual(level.analyse(job, self.folder), report)
            changed = copy.deepcopy(job); changed['slots'] = changed['slots'][:1]
            self.assertEqual(level.fingerprint(changed,self.folder),report['revision'])
        self.assertAlmostEqual(reports[1]['gain']/reports[0]['gain'], 2, delta=.03)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg required')
    def test_mono_output_peak_is_not_reduced_by_stereo_pan_law(self):
        path=self.folder/'mono.wav'
        with wave.open(str(path),'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(48000)
            out.writeframes(b''.join(struct.pack('<h',int(.95*32767*math.sin(2*math.pi*997*n/48000))) for n in range(96000)))
        _,peak=level.scan([path])
        self.assertAlmostEqual(peak,20*math.log10(.95),delta=.15)

    def test_individual_output_peaks_limit_gain_and_changes_invalidate_cache(self):
        self.tone('a.wav', .1); self.tone('b.wav', .2)
        job = {'slots':[{'slot':'BASS','file':'a.wav'},{'slot':'KEYS','file':'b.wav'}]}
        with patch.object(level, 'scan', side_effect=[(-22, -10),(-30,3),(-30,-20)]):
            report = level.analyse(job,self.folder)
        self.assertEqual(report['gain_db'], -6)
        self.assertTrue(report['limited'])
        self.tone('a.wav', .3)
        self.assertNotEqual(level.fingerprint(job,self.folder),report['revision'])

    def test_silent_sources_and_missing_files_never_invent_a_gain(self):
        self.tone('silent.wav',0)
        job={'slots':[{'slot':'BASS','file':'silent.wav'}]}
        with patch.object(level,'scan',return_value=(-70,float('-inf'))):
            self.assertNotIn('gain',level.analyse(job,self.folder))
        (self.folder/'silent.wav').unlink()
        with self.assertRaises(ValueError):level.analyse(job,self.folder)

    def test_lua_matching_preserves_manual_volume_balance_and_handles_legacy(self):
        lua=LuaRuntime(unpack_returned_tuples=True)
        lua.execute('''ext={};items={{gain=1,tag=''}, {gain=.5,tag=''}}
          reaper={GetProjExtState=function(_,s,k)return 1,ext[s..'/'..k] or '' end,
          SetProjExtState=function(_,s,k,v)ext[s..'/'..k]=v end,UpdateArrange=function()end,
          GetMediaItemInfo_Value=function(it)return it.gain end,
          SetMediaItemInfo_Value=function(it,_,v)it.gain=v end,
          GetSetMediaItemInfo_String=function(it,_,v,set)if set then it.tag=v end return true,it.tag end}
        ''')
        lua.globals().P=lua.execute((ROOT/'Requirements/ReaSet_Playback.lua').read_text(encoding='utf-8').replace("local J=dofile(dir..'ReaSet_JSON.lua')", "local J=dofile("+repr((ROOT/'Requirements/ReaSet_JSON.lua').as_posix())+")"))
        lua.execute('''P.items=function()return {{item=items[1]},{item=items[2]}}end
          song={id=1,key='song'};report={status='measured',revision='one',gain=.4}
          P.match(song,report,false);P.match(song,report,false)
        ''')
        self.assertAlmostEqual(lua.eval('items[2].gain'),.2)
        lua.execute("P.set(song,.25);report.gain=.3;P.match(song,report,false)")
        self.assertAlmostEqual(lua.eval('P.gain(song)'),.25)
        self.assertTrue(lua.eval('P.level(song).manual'))
        lua.execute('P.match(song,report,true)')
        self.assertAlmostEqual(lua.eval('items[1].gain'),.3)
        self.assertAlmostEqual(lua.eval('items[2].gain'),.15)
        self.assertFalse(lua.eval('P.level(song).manual'))
        lua.execute("ext['ReaSetGainMode/song']='';ext['ReaSetGain/song']='0.8';P.match(song,report,false)")
        self.assertAlmostEqual(lua.eval('P.gain(song)'),.8)
        self.assertTrue(lua.eval('P.level(song).manual'))
