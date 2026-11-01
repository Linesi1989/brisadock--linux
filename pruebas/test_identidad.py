import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from linux_desktop import DesktopIndex
from desktop_backend import application_target,merge_items,canonical

class IdentityTest(unittest.TestCase):
 def test_shared_interpreter_and_two_windows(self):
  with tempfile.TemporaryDirectory() as directory:
   entries=[]
   for name in ('Alpha','Beta'):
    p=Path(directory)/(name+'.desktop')
    p.write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec=/usr/bin/python3 /tmp/'+name+'.py\nStartupWMClass='+name+'\n')
    entries.append(dict(name=name,path=str(p)))
   index=DesktopIndex(entries)
   self.assertIsNone(index.resolve((),'/usr/bin/python3'))
   alpha=index.resolve(('alpha','Alpha'),'/usr/bin/python3')
   beta=index.resolve(('beta','Beta'),'/usr/bin/python3')
   self.assertNotEqual(alpha,beta)
   target=application_target(alpha['path'])
   self.assertEqual(target,alpha['path'])
   windows=[dict(id=i,key=canonical(target),path=target,name='Alpha') for i in (1,2)]
   items=merge_items([alpha],windows)
   self.assertEqual(len(items),1)
   self.assertEqual(len(items[0]['windows']),2)
   items=merge_items([alpha],windows[1:])
   self.assertEqual(items[0]['windows'][0]['id'],2)

if __name__=='__main__':unittest.main()
