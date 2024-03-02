#coding:utf-8
#author:bbbirder
import os
import platform
from os.path import join as pjoin,exists as pexists
import argparse
import commentjson as json
import subprocess
import pathvalidate

TEMPLATE_HOME_CONFIG = """{
    "home": "%s",
    "mappings": 
    {
        "folder1" : "{name}-folder1"
    }
}"""

TEMPLATE_PATCH_CONFIG = """{
    "dependencies": []
}"""

HOME_CONFIG_NAME = "sync-config.json"
PATCH_CONFIG_NAME = "patch-config.json"

_is_windows = "windows" in platform.system().lower()

def _update_modified_time(targetPath:str):
    if os.path.isfile(targetPath):
        os.utime(targetPath)
    elif os.path.isdir(targetPath):
        for (root,dirs,files) in os.walk(targetPath):
            for f in files:
                os.utime(pjoin(root,f))
    pass

def _shell(bin,*args):
    r = subprocess.run([bin,*args],capture_output=True,text=True,encoding="utf-8")
    if r.returncode != 0:
        raise Exception(r.stderr)
    return r.returncode,r.stdout

class PatchManager:
    def __init__(self,quiet:bool=False) -> None:
        if not pexists(HOME_CONFIG_NAME):
            raise Exception("not a valid project. please init first.")
        with open(HOME_CONFIG_NAME,"r",encoding="utf-8") as f:
            self.__config = json.load(f)
        self.__patch_home = self.__config["home"]
        self.mappings = self.__config["mappings"]
        self.patch_entries = set()
        self.__quiet = quiet
        for patch in self.get_patches():
            patch_root = pjoin(self.__patch_home,patch)
            for entry in os.listdir(patch_root):
                entry = pjoin(patch_root,entry)
                if os.path.exists(entry):
                    self.patch_entries.add(os.stat(entry).st_ino)
        pass

    def __log(self,*args):
        if not self.__quiet:
            print(*args)

    def __is_patch_link(self,path):
        # inode approach
        if not os.path.exists(path):
            return False
        home = os.path.abspath(self.__patch_home)
        apath = os.path.abspath(path)
        
        if apath.startswith(home):
            return False
        return os.stat(apath).st_ino in self.patch_entries
    
        # fsutil approach
    
        # home = os.path.abspath(self.__patch_home)
        # rpath = os.path.realpath(path)
        # apath = os.path.abspath(path)
        # if _is_windows and os.path.isfile(rpath): # for hard links
        #     targets = _get_shell_output("fsutil","hardlink","list",path).splitlines()
        #     for target in targets:
        #         if os.path.abspath(target).startswith(home):
        #             return True
        #     return False
        # if rpath==apath: # alternative way to os.path.islink
        #     return False
        # if not rpath.startswith(home):
        #     return False
        # return os.path.lexists(path)

    def get_patches(self):
        return [p for p in os.listdir(self.__patch_home) if os.path.isdir(pjoin(self.__patch_home,p))]

    def __make_link(self,link_path:str,target_path:str):
        self.__log(f"link {link_path} -> {target_path}")
        link_path = os.path.abspath(link_path)
        target_path = os.path.abspath(target_path)

        home = os.path.abspath(self.__patch_home)
        if link_path.startswith(home):
            raise Exception(f"you can't create link inside patches root! {link_path}->{home}")

        parent_path = os.path.dirname(link_path)
        os.makedirs(parent_path,exist_ok=True)

        _update_modified_time(target_path)
        if _is_windows:
            if os.path.isfile(target_path):
                _shell("cmd","/c",'mklink','/H',link_path,target_path)
            elif os.path.isdir(target_path):
                _shell("cmd","/c",'mklink','/J',link_path,target_path)
            else:
                raise Exception(f"target path not exists: {target_path}")
        else:
            _shell("ln","-s",link_path,target_path)
        
    def __delete_link(self,path):
        if self.__is_patch_link(path): # its a valid link from patches
            return os.remove(path)
        if not os.path.lexists(path): # a broken links
            try:
                return os.remove(path)
            except:
                pass
        if os.path.exists(path):
            raise Exception(f"Cannot safely delete target path: {path}, which is not a valid patch link. "
                "Remove it manually after making sure it's not an important work copy content")
        
    def clean_patches(self):
        self.__log("clean patches...")
        for (f,t) in self.mappings.items():
            if "{name}" in t:
                for patch in self.get_patches():
                    path = t.replace("{name}",patch)
                    self.__delete_link(path)
            else:
                self.__delete_link(t)

    def __extract_dependent_patches(self,patches:list[str]):
        visiting = set()
        visited = []
        def visit(patch):
            if patch in visiting:
                dep_path = "->".join(visiting)
                raise Exception(f"circular denpendency detected: {dep_path}")
            if patch in visited:
                visited.remove(patch)
                visited.append(patch)
            else:
                visiting.add(patch)
                for dep in self.get_patch_config(patch)["dependencies"]:
                    visit(dep)
                visiting.remove(patch)
                visited.append(patch)
        for patch in patches:
            visit(patch)
        return visited

    def get_patch_config(self,patch:str):
        config_path = pjoin(self.__patch_home,patch,"patch.config.json")
        config = {}
        if pexists(config_path):
            with open(config_path,"r",encoding="utf-8") as f:
                config = json.load(f)
        config.setdefault("dependencies",[])
        return config

    def apply_patches(self,patches:list[str]):
        self.clean_patches()
            
        mappings = {}
        deps = self.__extract_dependent_patches(patches)
        str_deps = ",".join(deps)
        self.__log(f"apply patches:{str_deps}...")
        for patch in deps:
            patch_root = pjoin(self.__patch_home,patch)
            for (f,t) in self.mappings.items():
                pfrom = pjoin(patch_root,f)
                pto = t.replace("{name}",patch)
                if not pexists(pfrom): continue
                mappings[pfrom] = pto
        for (f,t) in mappings.items():
            self.__make_link(t,f)
        self.__log("completed!")

if __name__=="__main__":
    def init_project(args):
        os.chdir(args["project"])

        if os.path.exists(HOME_CONFIG_NAME):
            raise Exception(f"project has already been inited")
        
        home = args["home"]
        if not home:
            home = input("the path to maintain patches: (game-patches)") or "game-patches"
        if not pathvalidate.is_valid_filename(home):
            raise Exception(f"{home} is not valid directory name")

        with open(HOME_CONFIG_NAME,"+xt") as f:
            f.write(TEMPLATE_HOME_CONFIG%home)
        os.makedirs(home,exist_ok=True)
        if not os.listdir(home):
            os.makedirs(pjoin(home,"patch-1"))
            os.makedirs(pjoin(home,"patch-1","folder1"))
            with open(pjoin(home,"patch-1",PATCH_CONFIG_NAME),"+xt") as f:
                f.write(TEMPLATE_PATCH_CONFIG)
            

    def list_patches(args):
        manager = PatchManager()
        for patch in manager.get_patches():
            print(patch)
    
    def apply_patches(args):
        manager = PatchManager(args["quiet"])
        manager.apply_patches(args["patches"])
        
    parser = argparse.ArgumentParser(description="patch 工具")
    subparsers = parser.add_subparsers(help="commands",required=True)
    
    list_parser = subparsers.add_parser("init", help="init a sync project")
    list_parser.add_argument("-p","--project",help="target project path",type=str,default=".")
    list_parser.add_argument("--home",help="the path to maintain patches",type=str)
    list_parser.set_defaults(func=init_project)

    list_parser = subparsers.add_parser("list", help="list all patches")
    list_parser.set_defaults(func=list_patches)
    
    apply_parser = subparsers.add_parser("apply", help="apply patches")
    apply_parser.add_argument("-q","--quiet",help="dont print log",action="store_true",default=False)
    apply_parser.add_argument("patches",nargs="+")
    apply_parser.set_defaults(func=apply_patches)
    
    args = parser.parse_args()
    args.func(vars(args))