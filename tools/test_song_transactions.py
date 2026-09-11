"""Execute the production Lua transaction against a deterministic REAPER API.
Install development dependencies with pip install -r tools/requirements-dev.txt.
"""
import json
import tempfile
import unittest
from pathlib import Path

from lupa import LuaRuntime

ROOT = Path(__file__).resolve().parent.parent


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        self.lua.globals().json_path=str(ROOT/'Requirements/ReaSet_JSON.lua')
        self.lua.execute('''
J=dofile(json_path)
tracks={{name="lyrics",items={{p=10,l=2,note="old lyric",guid="L"}}},
        {name="chords",items={{p=10,l=2,note="C",guid="C"}}}}
ext={['ReaSet/projectId']='P',['ReaSetCLRepair/song:1:lyrics']='10=11',
     ['ReaSetCLRepair/song:1:chords:reviewed']='1'}
playing=0;region_end=60;refresh=0
reaper={
 GetPlayState=function()return playing end,
 GetProjExtState=function(_,sec,key)return 1,ext[sec..'/'..key] or '' end,
 SetProjExtState=function(_,sec,key,value)ext[sec..'/'..key]=value;return 1 end,
 SetExtState=function()end,ShowConsoleMsg=function()end,
 EnumProjectMarkers2=function(_,i)if i==0 then return 1,true,0,region_end,'Song',1 end return 0 end,
 CountTracks=function()return #tracks end,GetTrack=function(_,i)return tracks[i+1]end,
 GetTrackName=function(tr)return true,tr.name end,
 CountTrackMediaItems=function(tr)return #tr.items end,
 GetTrackMediaItem=function(tr,i)return tr.items[i+1] end,
 GetMediaItemInfo_Value=function(it,key)if key=='D_POSITION'then return it.p elseif key=='B_MUTE'then return it.mute or 0 else return it.l end end,
 GetActiveTake=function()return nil end,
 GetItemStateChunk=function(it)return true,J.encode(it)end,
 SetItemStateChunk=function(it,chunk)local restored=J.decode(chunk);for k in pairs(it)do it[k]=nil end;for k,v in pairs(restored)do it[k]=v end;return true end,
 DeleteTrackMediaItem=function(tr,it)for i,x in ipairs(tr.items)do if it==x then table.remove(tr.items,i);return true end end end,
 AddMediaItemToTrack=function(tr)local it={guid='new-'..(#tr.items+1)};table.insert(tr.items,it);return it end,
 SetMediaItemInfo_Value=function(it,key,v)if key=='D_POSITION'then it.p=v elseif key=='B_MUTE'then it.mute=v else it.l=v end end,
 ULT_SetMediaItemNote=function(it,note)if fail_note then fail_note=false;error('injected failure')end;it.note=note end,
 Undo_BeginBlock=function()end,Undo_EndBlock=function()end,UpdateArrange=function()end,MarkProjectDirty=function()end,
 TrackList_AdjustWindows=function()end,
 PCM_Source_CreateFromFile=function(path)return {file=path}end,
 GetMediaSourceLength=function()return 60 end,PCM_Source_Destroy=function()end,
 AddTakeToMediaItem=function(it)it.take={};return it.take end,
 SetMediaItemTake_Source=function(take,src)take.source=src end,
 GetSetMediaItemTakeInfo_String=function(take,key,value)take.name=value;return true,value end,
 GetSetMediaItemInfo_String=function(it,key,value,set)if set then it.owned=value end;return true,it.owned or '' end,
 PreventUIRefresh=function(n)refresh=refresh+n end
}
real_dofile=dofile
dofile=function(path)if path:match('jamroom_pending_rechord.lua$')then return job end;return real_dofile(path)end
''')

    def tearDown(self):self.tmp.cleanup()

    def run_job(self, operation='one', **kwargs):
        folder=self.folder/operation;folder.mkdir(exist_ok=True)
        job={'project':'P','id':1,'region':'Song','start':0,'end':60,'operation':operation,
             'before':str(folder/'before.json'),'after':str(folder/'after.json'),'receipt':str(folder/'receipt.json'),
             'lyrics':[{'s':20,'e':22,'text':'new lyric'}], 'chords':[{'s':20,'e':22,'name':'G'}],
             'document':json.dumps({'schema':2,'sections':[],'revision':'new'}),'revision':'new'}
        job.update(kwargs)
        job={k:v for k,v in job.items() if v is not None}
        self.lua.globals().job_json=json.dumps(job)
        self.lua.execute('job=J.decode(job_json)')
        self.lua.globals().transaction=str(ROOT/'tools/jamroom_song_transaction.lua')
        self.lua.execute('real_dofile(transaction)')
        return json.loads((folder/'receipt.json').read_text()),folder

    def test_replace_clears_repairs_and_snapshots_actual_items(self):
        reply,folder=self.run_job()
        self.assertEqual(reply['status'],'ok')
        self.assertEqual(self.lua.eval('tracks[1].items[1].note'),'new lyric')
        self.assertEqual(self.lua.eval("ext['ReaSetCLRepair/song:1:lyrics']"),'')
        self.assertTrue((folder/'before.json').exists());self.assertTrue((folder/'after.json').exists())
        self.assertEqual(self.lua.eval('refresh'),0)

    def test_idempotent_retry_does_not_overwrite_original_snapshot(self):
        _,folder=self.run_job();before=(folder/'before.json').read_bytes()
        reply,_=self.run_job()
        self.assertEqual(reply['message'],'Already applied')
        self.assertEqual((folder/'before.json').read_bytes(),before)

    def test_restore_recovers_notes_and_repairs(self):
        _,folder=self.run_job()
        reply,_=self.run_job('restore',restore=str(folder/'before.json'),expected=str(folder/'after.json'))
        self.assertEqual(reply['status'],'ok')
        self.assertEqual(self.lua.eval('tracks[1].items[1].note'),'old lyric')
        self.assertEqual(self.lua.eval("ext['ReaSetCLRepair/song:1:lyrics']"),'10=11')

    def test_restore_refuses_to_overwrite_new_edit(self):
        _,folder=self.run_job();self.lua.execute("tracks[1].items[1].note='human edit'")
        reply,_=self.run_job('restore',restore=str(folder/'before.json'),expected=str(folder/'after.json'))
        self.assertEqual(reply['status'],'error')
        self.assertEqual(self.lua.eval('tracks[1].items[1].note'),'human edit')

    def test_invalid_item_and_changed_region_are_rejected_before_delete(self):
        for args in ({'chords':[{'s':70,'e':80,'name':'G'}]}, {'end':59}, {'project':'wrong'}):
            with self.subTest(args=args):
                reply,_=self.run_job(**args)
                self.assertEqual(reply['status'],'error')
                self.assertEqual(self.lua.eval('tracks[1].items[1].note'),'old lyric')

    def test_failed_mutation_restores_previous_state(self):
        self.lua.execute('fail_note=true')
        reply,_=self.run_job()
        self.assertEqual(reply['status'],'error')
        self.assertEqual(self.lua.eval('tracks[1].items[1].note'),'old lyric')
        self.assertEqual(self.lua.eval('tracks[2].items[1].note'),'C')
        self.assertEqual(self.lua.eval('refresh'),0)

    def test_playing_project_is_not_changed(self):
        self.lua.execute('playing=1')
        reply,_=self.run_job();self.assertEqual(reply['status'],'error')
        self.assertEqual(self.lua.eval('tracks[1].items[1].note'),'old lyric')

    def test_click_only_replace_and_restore_keep_chart_and_other_audio(self):
        self.lua.execute("table.insert(tracks,{name='[JR:CLICK] Click',items={}})")
        original=self.lua.eval('J.encode({tracks[1],tracks[2]})')
        args={'lyrics':None,'chords':None,'document':None,'revision':None}
        reply,folder=self.run_job('click',click={'file':'test.wav','revision':'click-1','muted':True},**args)
        self.assertEqual(reply['status'],'ok',reply)
        self.assertEqual(self.lua.eval('J.encode({tracks[1],tracks[2]})'),original)
        self.assertEqual(self.lua.eval('#tracks[3].items'),1)
        self.assertEqual(self.lua.eval('tracks[3].items[1].mute'),1)
        self.assertEqual(self.lua.eval('tracks[3].items[1].l'),60)
        reply,_=self.run_job('restore-click',restore=str(folder/'before.json'),expected=str(folder/'after.json'),**args)
        self.assertEqual(reply['status'],'ok',reply)
        self.assertEqual(self.lua.eval('#tracks[3].items'),0)
        self.assertEqual(self.lua.eval('J.encode({tracks[1],tracks[2]})'),original)

    def test_click_update_refuses_an_unowned_existing_click(self):
        self.lua.execute("table.insert(tracks,{name='[JR:CLICK] Click',items={{p=0,l=60,note='My click'}}})")
        reply,_=self.run_job(click={'file':'test.wav','revision':'click-1'})
        self.assertEqual(reply['status'],'error')
        self.assertEqual(self.lua.eval('tracks[3].items[1].note'),'My click')

    def test_json_roundtrip_unicode_arrays_and_null(self):
        value={'words':'é 🎵 \\ "','empty':[], 'bool':False, 'null':None}
        self.lua.globals().payload=json.dumps(value)
        self.assertEqual(json.loads(self.lua.eval('J.encode(J.decode(payload))')),value)


if __name__=='__main__':unittest.main()
