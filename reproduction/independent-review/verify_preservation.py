"""Independent local preservation review; no API or Git mutation.

Reads canonical Git blobs, reverses the supplied citation ledger independently,
then executes only the offline adapter in an isolated shadow with file-access,
network and subprocess guards. Does not import the adapter or run science.
"""
from pathlib import Path
from collections import Counter
import argparse, ast, hashlib, json, re, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
H = '83583b1524778b8bb4e5c78482ae7f4f104856cc'
TREE = '7bf82539dd5224ec9328dc94848b2a62dc6b4029'
R = '459dc1824f2d16fae146be32a7caffba703e5aca'
AP_SHA = 'f3721435cf588fba159e53d90ef8a61824ad3f61b793baa8b2cf1fa64fb1f69f'
AAES_SHA = '027a036caf6b7eaeb1577d478a350e7261163ba922dac9d8f155b5e38e3e5783'
HEADINGS = ['Introduction','Related Work','Methodology','Results','Discussion','Limitations','Conclusion']
MATH = re.compile(r'\\\[.*?\\\]|\\\(.*?\\\)|\$\$.*?\$\$|(?<![\\$])\$(?!\$).*?(?<!\\)\$(?!\$)',re.S)
IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

def sha(raw): return hashlib.sha256(raw).hexdigest()
def load(path): return json.loads(path.read_bytes())
def sections(text):
    matches=list(re.finditer(r'^## (.+)$',text,re.M))
    return [(m[1],text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()) for i,m in enumerate(matches)]
def rawfiles(root):
    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts and '__pycache__' not in p.parts and not p.name.endswith('.pyc')}

def main():
    if not __debug__: raise RuntimeError('Independent preservation assertions require ordinary Python; -O is rejected.')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--canonical-repo',type=Path,required=True)
    parser.add_argument('--agentpub-payload',type=Path,required=True)
    parser.add_argument('--aaes-registration',type=Path,required=True)
    parser.add_argument('--shadow-parent',type=Path,required=True)
    args=parser.parse_args()
    before=rawfiles(ROOT)
    inventory=load(ROOT/'reproduction/pinned-inputs.json')
    checks=load(ROOT/'reproduction/adapter-checks.json')
    assert (ROOT/'reproduction/adapter-checks.json').read_bytes()==(ROOT/'reproduction/canonical-preservation-v1.0.0.json').read_bytes()
    assert inventory['computational_commit']==H and inventory['computational_tree']==TREE and inventory['canonical_content_commit']==R
    entries=inventory['files'];assert len(entries)==72 and len({x['package_path'] for x in entries})==72
    roles=Counter(); verified=[]
    for row in entries:
        rev=row['source_revision'];roles[rev]+=1;assert rev in [H,R]
        local=(ROOT/row['package_path']).read_bytes()
        blob=subprocess.run(['git','-C',str(args.canonical_repo),'show',rev+':'+row['source_path']],capture_output=True,check=True).stdout
        assert blob==local and len(blob)==row['bytes'] and sha(blob)==row['sha256']
        assert row['package_path']=='reproduction/canonical/'+row['source_path']
        verified.append({'path':row['package_path'],'revision':rev,'bytes':len(blob),'sha256':sha(blob)})
    assert roles==Counter({H:55,R:17})
    assert subprocess.run(['git','-C',str(args.canonical_repo),'rev-parse',H+'^{tree}'],capture_output=True,text=True,check=True).stdout.strip()==TREE
    canonical=(ROOT/'reproduction/canonical/paper/manuscript.md').read_text(encoding='utf-8')
    source_sections=sections(canonical);source_map=dict(source_sections)
    numbered=[(h,b) for h,b in source_sections if re.match(r'^[1-6]\. ',h)]
    assert len(numbered)==6 and list(source_map)==['Abstract',*[h for h,b in numbered],'References']
    science='\n\n'.join(b for h,b in numbered)
    apraw=args.agentpub_payload.read_bytes();aaesraw=args.aaes_registration.read_bytes()
    assert sha(apraw)==AP_SHA and sha(aaesraw)==AAES_SHA
    ap=json.loads(apraw);aaes=json.loads(aaesraw)
    assert ap['paper_type']=='short_communication' and [s['heading'] for s in ap['sections']]==HEADINGS
    assert ap['authors']==[{'agent_id':'agent_29b9bf7a','display_name':'Lattice Audit Agent','model_type':'not recorded'}]
    assert '**Taylor Kalin**' in canonical.split('## Abstract')[0]
    assert ap['metadata']['agent_model']=='not recorded' and ap['metadata']['total_tokens']==-1
    assert ap['metadata']['agent_platform']=='Codex desktop'
    assert 'human operator and canonical author Taylor Kalin' in ap['metadata']['submission_note']
    assert ap['abstract']==source_map['Abstract']
    assert ap['metadata']['submission_note'].endswith(source_map['References'])
    ledger=checks['citation_format']['reversal_ledger_by_section']; restored=[]; occurrence_count=0
    refids={r['ref_id'] for r in ap['references']};assert refids==set(map(str,range(1,6)))
    for group in ap['sections']:
        content=group['content'];rows=ledger[group['heading']]
        assert rows==sorted(rows,key=lambda r:r['adapted_start'])
        last=0
        for row in rows:
            start,end=row['adapted_start'],row['adapted_end']
            assert last<=start<end<=len(content) and content[start:end]==row['adapted']
            assert set(row['reference_ids'])<=refids
            assert not any(start<m.end() and end>m.start() for m in MATH.finditer(content))
            last=end;occurrence_count+=1
        assert group['citations']==sorted({x for row in rows for x in row['reference_ids']},key=int)
        for row in reversed(rows):
            content=content[:row['adapted_start']]+row['canonical']+content[row['adapted_end']:]
        restored.append(content)
    assert occurrence_count==12
    restored='\n\n'.join(restored)
    route_map={}
    for alt,old in IMAGE.findall(science):
        remote='https://raw.githubusercontent.com/Teylersf/electron-only-equation-audit/'+H+'/figures/'+old.rsplit('/',1)[1]
        local='reproduction/canonical/figures/'+old.rsplit('/',1)[1]
        route_map[old]=(local,remote)
        assert IMAGE.findall(restored).count((alt,remote))==1
        restored=restored.replace(']('+remote+')',']('+old+')')
    for heading in checks['added_platform_headings']:
        assert restored.count(heading+'\n\n')==1
        restored=restored.replace(heading+'\n\n','',1)
    assert len(checks['added_platform_headings'])==4 and restored==science
    local_paper=(ROOT/'paper.md').read_text(encoding='utf-8')
    assert (ROOT/'paper.md').read_bytes()==(ROOT/'agent-paper.md').read_bytes()
    local_sections=sections(local_paper);local_map=dict(local_sections)
    local_bodies=[]
    for h,b in local_sections:
        if re.match(r'^[1-6]\. ',h):
            for old,(local,remote) in route_map.items():b=b.replace(']('+local+')',']('+old+')')
            local_bodies.append((h,b))
    assert local_bodies==numbered
    assert local_map['Abstract']==source_map['Abstract'] and local_map['References']==source_map['References']
    assert '**Lattice Audit Agent**' in local_paper.split('## Abstract')[0] and 'canonical author: **Taylor Kalin**' in local_paper.split('## Abstract')[0]
    assert MATH.findall(restored)==MATH.findall(science) and len(MATH.findall(science))==99
    assert re.findall(r'\\tag\{([^{}]+)\}',science)==list(map(str,range(1,13)))
    assert len(IMAGE.findall(science))==2
    assert len(re.findall(r'^Figure [12]\. .+$',science,re.M))==2
    refs=re.findall(r'^\[(\d+)\] (.+?)(?=\n\n\[\d+\] |\Z)',source_map['References'],re.M|re.S)
    assert len(refs)==5
    for record,normalized in zip(refs,ap['references']):
        assert record[0]==normalized['ref_id'] and normalized['title']+'.' in record[1]
        assert 'https://doi.org/'+normalized['doi'] in record[1] and str(normalized['year']) in record[1]
        assert all(a in record[1].split(normalized['title'],1)[0] for a in normalized['authors'])
    limits=load(ROOT/'reproduction/agentpub-paper-schema.json')['paper_types']['short_communication']['constraints']
    words=lambda t:len(re.findall(r"\b[\w'-]+\b",t))
    body_words=sum(words(s['content']) for s in ap['sections'])
    assert 1500<=body_words<=4000 and words(ap['abstract'])<=500 and len(ap['title'])<=200
    assert set(limits['sections']['required'])<=set(HEADINGS)
    assert [h for h in limits['sections']['must_appear_in_this_order'] if h in HEADINGS]==HEADINGS
    assert 1<=len(ap['tags'])<=10 and all(len(x)<=50 for x in ap['tags'])
    maxunits=max(len(s['content'].encode('utf-16-le'))//2 for s in ap['sections']);assert maxunits<=49000
    context=load(ROOT/'reproduction/submission-context.json')
    for key in ['AgentPub_submission_gate_open','AAES_submission_gate_open','own_Publishfun_final_disposition_verified','formal_submission_performed','public_agent_repository_verified']:assert context[key] is False
    assert len(aaes['claims'])==5 and aaes['source']=='github:Teylersf/electron-only-equation-agent-publication'
    meta=load(ROOT/'metadata.json');assert meta['author_ids']==['gist:7c74312cf47dcc31c789a8b1c3dedd25'] and meta['timestamp_scope']=='local preparation, not registration'
    code=(ROOT/'reproduction/prepare_packages.py').read_bytes()
    parsed=ast.parse(code); imports=[]
    for node in ast.walk(parsed):
        if isinstance(node,ast.Import):imports.extend(n.name for n in node.names)
        if isinstance(node,ast.ImportFrom):imports.append(node.module)
    assert set(imports)<={'__future__','argparse','collections','datetime','hashlib','json','pathlib','re','sys'}
    assert checks['preparer_sha256']==sha(code)
    # This parent-supplied shadow path remains on disk for audit; no recursive deletion.
    args.shadow_parent.mkdir(parents=True,exist_ok=True)
    shadow=Path(tempfile.mkdtemp(prefix='source10-agent-independent-',dir=args.shadow_parent))
    clone=shadow/'package';shutil.copytree(ROOT,clone,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc'))
    out=shadow/'outgoing'
    argv=[str(clone/'reproduction/prepare_packages.py'),'--outgoing-dir',str(out),'--expected-code-commit',H,'--expected-code-tree',TREE,'--canonical-content-commit',R,'--expected-manuscript-sha256',checks['canonical_manuscript_sha256'],'--expected-pdf-sha256',checks['canonical_PDF_sha256'],'--expected-input-inventory-sha256',checks['pinned_input_inventory_sha256']]
    guard="""import sys,runpy,pathlib,socket,subprocess,os
allowed=[pathlib.Path(sys.argv[1]).resolve(),pathlib.Path(sys.base_prefix).resolve(),pathlib.Path(sys.prefix).resolve()]
denied={'network':0,'external_file':0,'subprocess':0}
def audit(event,args):
 if event.startswith('socket.'):
  denied['network']+=1;raise PermissionError('Network disabled in preservation shadow')
 if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn'):
  denied['subprocess']+=1;raise PermissionError('Subprocess disabled in preservation shadow')
 if event=='open' and not isinstance(args[0],int):
  p=pathlib.Path(args[0]).resolve()
  if not any(p.is_relative_to(a) for a in allowed):
   denied['external_file']+=1;raise PermissionError('External files and credential vault disabled')
sys.addaudithook(audit)
try:socket.socket();raise RuntimeError('network guard missing')
except PermissionError:pass
try:open(pathlib.Path(sys.argv[1]).parent/'vault-disabled-probe');raise RuntimeError('file guard missing')
except PermissionError:pass
try:subprocess.Popen(['never-run']);raise RuntimeError('process guard missing')
except PermissionError:pass
sys.argv=sys.argv[2:]
runpy.run_path(sys.argv[0],run_name='__main__')
print('GUARDED_SHADOW_COMPLETE')
"""
    run=subprocess.run([sys.executable,'-I','-c',guard,str(shadow),*argv],capture_output=True,text=True,check=True)
    assert 'GUARDED_SHADOW_COMPLETE' in run.stdout
    assert (out/'electron-only-agentpub-payload.json').read_bytes()==apraw
    assert (out/'electron-only-aaes-registration.json').read_bytes()==aaesraw
    deterministic=['paper.md','agent-paper.md','README.md','reproduction/README.md','.gitattributes','.gitignore','LICENSE-CODE','LICENSE-MANUSCRIPT']
    assert all((clone/p).read_bytes()==(ROOT/p).read_bytes() for p in deterministic)
    timestamps={'metadata.json':'submitted_at','reproduction/submission-context.json':'prepared_at_utc','reproduction/adapter-checks.json':'prepared_at_utc','reproduction/canonical-preservation-v1.0.0.json':'prepared_at_utc'}
    for name,key in timestamps.items():
        a,b=load(clone/name),load(ROOT/name);a.pop(key);b.pop(key);assert a==b
    shadow_before=rawfiles(clone)
    optimized=subprocess.run([sys.executable,'-I','-O',*argv],capture_output=True,text=True)
    assert optimized.returncode!=0 and 'Ordinary Python required' in optimized.stderr
    assert rawfiles(clone)==shadow_before
    assert rawfiles(ROOT)==before
    # Generic independent public-safety scan; validation regex literals and declared
    # immutable exclusion patterns are not private filesystem locations.
    forbidden=[]
    for path,raw in before.items():
        if raw.startswith(b'%PDF') or raw.startswith(b'\x89PNG'):continue
        try:t=raw.decode('utf-8')
        except UnicodeDecodeError:continue
        if re.search(r'(?i)(?:[EG]:[\\/](?:ALIVE|Research)|C:[\\/]Users[\\/]|Bearer\s+[A-Za-z0-9._-]{16,}|gh[pousr]_[A-Za-z0-9]{20,})',t):forbidden.append(path)
    assert not forbidden
    report={'status':'passed','scope':'Independent raw Git-blob/citation/text/schema/byline/safety review and guarded offline shadow only; no API, Git mutation, source scientific rerun or publication.',
      'computational_commit':H,'computational_tree':TREE,'canonical_content_commit':R,
      'adapter_sha256':sha(code),'adapter_checks_sha256':sha((ROOT/'reproduction/adapter-checks.json').read_bytes()),'pinned_inventory_sha256':sha((ROOT/'reproduction/pinned-inputs.json').read_bytes()),
      'agentpub_payload_sha256':AP_SHA,'AAES_registration_sha256':AAES_SHA,
      'raw_git_copy_counts':{'computational':55,'release_support':17,'total':72},'all_pinned_copies_raw_byte_exact':True,
      'scientific_restoration':{'six_local_bodies_exact':True,'seven_API_groups_exact_after_declared_reversal':True,'all_original_ordered_math_exact':99,'numbered_tags':list(range(1,13)),'full_figure_caption_pairs':2,'complete_bibliography_records':5,'abstract_exact':True,'prose_citation_occurrences_reversed':12,'source_subheadings_added_and_removed':4,'no_scientific_omission_or_padding':True},
      'format_and_identity':{'paper_type':'short_communication','body_regex_words':body_words,'max_section_UTF16_units':maxunits,'schema_required_sections_order_fields_limits':'passed','agent_name':'Lattice Audit Agent','agent_id':'agent_29b9bf7a','canonical_author_and_human_operator':'Taylor Kalin','unrecorded_usage_sentinel':-1,'formal_gates_closed':True},
      'offline_shadow':{'status':'passed','imports_are_stdlib_only':True,'network_disabled':True,'vault_and_other_external_file_access_disabled':True,'subprocess_disabled_inside_adapter':True,'guards_probed_before_adapter':True,'payloads_and_local_science_byte_identical':True,'administrative_products_identical_except_declared_top_level_timestamps':True,'optimized_execution_rejected_without_file_changes':True,'original_inputs_unchanged':True},
      'public_safety':{'credential_or_private_location_matches':forbidden,'no_outgoing_payload_files_bundled':not any('outgoing' in p or 'payload.json' in p for p in before)},
      'public_readiness_recommendation':'Ready for root-controlled GitHub companion publication after root review; all science preserved. Formal AgentPub/AAES gates remain closed and no eligibility, acceptance or public viewer fidelity is inferred.',
      'review_program_sha256':sha(Path(__file__).read_bytes()),'verified_pinned_inputs':verified}
    dest=ROOT/'reproduction/independent-preservation-checks.json';dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'status':'passed','receipt_sha256':sha(dest.read_bytes()),'copy_count':72,'math':99,'tags':12,'figure_pairs':2,'references':5,'adapter_sha256':sha(code),'payload_sha256':AP_SHA},indent=2))

if __name__=='__main__':main()
