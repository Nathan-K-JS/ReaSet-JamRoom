// Generated from the native performance paginator by embed_chart_author.py.
function transposeChordName(s,n){return s;}
        function chartRowKey(row,si,ri){return row.id||('legacy-'+(si+1)+'-'+(ri+1));}
        function chartFragments(row,cols,mode,si,ri,semis){
            var text=String(row.text||''), anchors=(row.anchors||[]).map(function(a){return {offset:a.offset,symbol:transposeChordName(a.symbol,semis)};});
            var decorations='',repeat=row.repeat||1;
            if(mode==='chart'){
                // Chords-only keeps each written line/pattern; it is not a second lyric view.
                var symbols=anchors.map(function(a){return a.symbol;});
                if(!symbols.length)symbols=(row.progression||[]).map(function(x){return transposeChordName(x,semis);});
                var at=row.repeat_at===undefined?symbols.length:row.repeat_at;
                if(repeat>1)symbols.splice(at,0,'x'+repeat);
                decorations=symbols.join('   ');anchors=[];text='';
            }else if(mode==='lyrics'){
                anchors=[];
                if(!text.trim())return [];
            }else{
                // Preserve bars/repeat marks between source chords, never print them as lyrics.
                var raw=String(row.chord_line||'');
                var chars=raw.split('');
                (row.anchors||[]).forEach(function(a){for(var n=a.offset;n<a.offset+(a.width||a.symbol.length);n++)chars[n]=' ';});
                decorations=chars.join('');
                if(!raw && repeat>1)decorations=' '.repeat(Math.max(text.length,anchors.reduce(function(n,a){return Math.max(n,a.offset+a.symbol.length);},0))+2)+'x'+repeat;
                // Transposition can turn tightly printed C C C into C#C#C#.
                // Expand only instrumental space or space after the lyric;
                // anchors over words retain their exact authored columns.
                var previousEnd=-2;
                anchors.forEach(function(a,i){
                    if(a.offset>=text.length && a.offset<previousEnd+2){
                        var at=a.offset,extra=previousEnd+2-at;
                        decorations=decorations.slice(0,at)+' '.repeat(extra)+decorations.slice(at);
                        for(var j=i;j<anchors.length;j++)anchors[j].offset+=extra;
                    }
                    previousEnd=a.offset+a.symbol.length;
                });
            }
            var width=Math.max(text.length,decorations.length,anchors.reduce(function(n,a){return Math.max(n,a.offset+a.symbol.length);},0));
            if(!width)return [];
            var out=[],start=0;
            while(start<width){
                var end=Math.min(width,start+cols);
                if(end<width){
                    // Break only at a word boundary, moving any overhanging chord with its column.
                    if(text.length>end && text[end]!==' ' && text[end-1]!==' '){
                        var space=text.lastIndexOf(' ',end-1);if(space>start+cols*.45)end=space+1;
                    }
                    anchors.forEach(function(a){if(a.offset<end && a.offset+a.symbol.length>end && a.offset>start)end=a.offset;});
                    if(mode==='chart'){
                        var gap=decorations.lastIndexOf(' ',end-1);if(gap>start+cols*.45)end=gap+1;
                    }
                }
                if(end<=start)end=Math.min(width,start+cols);
                out.push({text:text.slice(start,end),decorations:decorations.slice(start,end),
                    anchors:anchors.filter(function(a){return a.offset>=start && a.offset<end;}).map(function(a){return {symbol:a.symbol,offset:a.offset-start};}),
                    column:start,row:chartRowKey(row,si,ri),rowIndex:ri,cue:row.cue,pageCues:row.page_cues||{},hasWords:mode!=='chart' && !!text.length,
                    hasChords:mode!=='lyrics' && (anchors.length>0 || !!decorations.trim())});
                start=end;
            }
            return out;
        }
        function chartBuildPages(doc,width,height,mode,semis){
            var pages=[];
            doc.sections.forEach(function(section,si){
                var preferred=width>=1000?28:22, font=preferred, fragments=[],budget;
                function layout(size){
                    var cols=Math.max(12,Math.floor((width-32)/(size*.61))),out=[];
                    (section.rows||[]).forEach(function(row,ri){out=out.concat(chartFragments(row,cols,mode,si,ri,semis));});
                    if(!out.length && mode!=='lyrics')out=chartFragments({text:'',progression:section.progression||[],anchors:[],repeat:section.repeat||1},cols,'chart',si,0,semis);
                    return out;
                }
                function cost(f){return (f.hasWords?1.35:0)+(f.hasChords?1.2:0)+.45;}
                for(var size=preferred;size>=20;size--){
                    var trial=layout(size),room=Math.max(3.1,(height-280)/size);
                    if(trial.reduce(function(n,f){return n+cost(f);},0)<=room){font=size;break;}
                }
                fragments=layout(font);budget=Math.max(3.1,(height-280)/font);
                // Pack whole lyric rows whenever they fit. Optimise page count
                // first, then balance space: a guessed target height could make
                // three pages where two fit and orphan the final riff.
                var blocks=[];
                fragments.forEach(function(f){
                    var last=blocks[blocks.length-1];
                    if(last && last.row===f.row && last.cost+cost(f)<=budget){last.parts.push(f);last.cost+=cost(f);}
                    else blocks.push({row:f.row,parts:[f],cost:cost(f)});
                });
                var best=[{count:0,score:0,previous:0}];
                for(var end=1;end<=blocks.length;end++){
                    var sum=0,choice=null;
                    for(var begin=end-1;begin>=0;begin--){
                        sum+=blocks[begin].cost;if(sum>budget+.001)break;
                        var prior=best[begin],score=prior.score+Math.pow(budget-sum,2),count=prior.count+1;
                        if(!choice || count<choice.count || (count===choice.count && score<choice.score))choice={count:count,score:score,previous:begin};
                    }
                    best.push(choice);
                }
                var sectionPages=[];
                for(var end=blocks.length;end>0;){
                    var begin=best[end].previous,parts=[];
                    for(var k=begin;k<end;k++)parts=parts.concat(blocks[k].parts);
                    sectionPages.unshift({section:si,parts:parts,font:font});end=begin;
                }
                if(!sectionPages.length)sectionPages.push({section:si,parts:[],font:font});
                sectionPages.forEach(function(p,i){
                    p.part=i;p.total=sectionPages.length;
                    var first=p.parts[0], guess=section.start+(section.end-section.start)*i/sectionPages.length;
                    var manual=first && first.pageCues[String(first.column)];
                    var candidate=manual===undefined?(first && first.cue):manual;
                    p.cue=i===0?section.start:(Number.isFinite(candidate) && candidate>section.start && candidate<section.end?candidate:guess);
                    // Two fragments of one lyric line cannot turn the page at the same cue.
                    if(i>0)p.cue=Math.max(sectionPages[i-1].cue+.01,Math.min(p.cue,section.end-.01*(sectionPages.length-i)));
                    p.checked=i===0?section.confidence==='section checked':Number.isFinite(manual)&&Math.abs(p.cue-manual)<.001;
                    pages.push(p);
                });
            });
            return pages;
        }
