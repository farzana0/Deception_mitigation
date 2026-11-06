"""Checksummed archive with fresh-directory table regeneration and PDF structure checks."""
import argparse,hashlib,json,subprocess,sys,tarfile,tempfile
from pathlib import Path
def sha(path):
 digest=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(8*1024*1024),b''):digest.update(block)
 return digest.hexdigest()
def seal(root,archive):
 assert not archive.is_relative_to(root),'Archive must be outside package'
 files=sorted(p for p in root.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and '__pycache__' not in p.parts)
 (root/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(root))+'\n' for p in files))
 archive.parent.mkdir(parents=True,exist_ok=True)
 with tarfile.open(archive,'w:gz',compresslevel=6) as tar:
  tar.add(root,arcname=root.name,filter=lambda member:None if '__pycache__' in Path(member.name).parts else member)
 with tempfile.TemporaryDirectory(prefix='cais-sealed-check-') as directory:
  destination=Path(directory).resolve()
  with tarfile.open(archive,'r:gz') as tar:
   for member in tar.getmembers():
    assert (member.isfile() or member.isdir()) and (destination/member.name).resolve().is_relative_to(destination),'Unsafe archive entry'
   tar.extractall(destination)
  fresh=destination/root.name
  checked=0
  for line in (fresh/'SHA256SUMS').read_text().splitlines():
   expected,name=line.split('  ',1);assert sha(fresh/name)==expected,name;checked+=1
  expected=(fresh/'report/tables/verified_tables.json').read_bytes()
  subprocess.run([sys.executable,str(fresh/'experiments/code/scripts/submission_tables.py'),'--package',str(fresh)],check=True)
  assert (fresh/'report/tables/verified_tables.json').read_bytes()==expected,'Fresh-directory table mismatch'
  from PIL.PdfParser import PdfParser
  with PdfParser(filename=str(fresh/'report/report.pdf')) as pdf:
   pages=len(pdf.pages);assert pages>=1
 result={'archive':str(archive),'sha256':sha(archive),'archived_file_checksums_verified':checked,'fresh_directory_main_tables':'passed','pdf_structure':'passed','pdf_pages':pages}
 archive.with_name(archive.name+'.sha256').write_text(result['sha256']+'  '+archive.name+'\n')
 archive.with_name(archive.name+'.verification.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);a=p.parse_args();seal(a.package.resolve(),a.archive.resolve())
