"""Define a fortran namelist file class"""
import os
import re
try:
    import numpy as np
except:
    print "ERROR: Couldn't import numpy, may well find errors later on."

#Some settings
DEBUG=False

#Regexp, should probably put this in an external file to be imported
_NmlStartReg=re.compile(r"^ *&([^ !]+)")
#Note this is very general
_NmlEndReg=re.compile(r"(^[^!]* |^ *)/") 
#Note here we assume there will never be a variable with ! in it's name
#and the value will never contain !
_KeyValSplit=re.compile(r"^([ a-zA-Z_]+)=([^!/]+)(!.*)?$")
#/Type regexp
_True=re.compile(r"^(\.t\.|\.true\.|t|true)$",re.I)
_False=re.compile(r"^(\.f\.|\.false\.|f|false)$",re.I)
_Array=re.compile(r"^([^()]*,)+")
_String=re.compile(r"^(\'.+\'|\".+\")$")
_NumString=r"^[+-]?[0-9]+\.?[0-9]*([de]?[+-]?[0-9]+)?$"
_Number=re.compile(r"^"+_NumString+r"$",re.I)
_Int=re.compile(r"^[+-]?[0-9]+$")
_Complex=re.compile(r"^\(("+_NumString+r"),("+_NumString+r")\)$")

class FortranNamelistFile:
    """A class representing a fortran namelist file."""
    def __init__(self,Filename=None):
        if not os.path.exists(Filename):
            raise(IOError("Filename '"+Filename+"' doesn't exist"))
        
        #Open the file and read all the lines
        if DEBUG:
            print "Reading file '{F}'".format(F=Filename)
        with open(Filename,'r') as ff:
            Lines=map(lambda x:x.strip(),ff.readlines())

        #Loop through lines to find namelist specifiers
        self.NmlNames=[]
        LineStart=[]
        LineEnd=[]
        for num,Line in enumerate(Lines):
            #Does line match the namelist regex
            tmp=_NmlStartReg.match(Line)
            #If match
            if not tmp is None:
                self.NmlNames.append(tmp.groups()[0])
                LineStart.append(num)

            #Does line match the end of namelist regex
            #Note that strictly a line can both start and end a namelist
            #so we have to test all lines for both.
            tmp=_NmlEndReg.match(Line)
            if not tmp is None:
                LineEnd.append(num)

        #Count the namelists
        self.NumNml=self.NmlNames.__len__()
        if self.NumNml==0:
            raise(RuntimeError("No namelists present in file."))

        #Make sure we have the right number of starts and ends
        if not self.NumNml == LineEnd.__len__():
            raise(RuntimeError("Mismatch in number of starts ({S}) and ends ({E})".format(
                        S=self.NumNml,E=LineEnd.__len__())))

        #Some debug reporting
        if DEBUG:
            print "-- Contains {N} namelists".format(N=self.NumNml)
            for num,j in enumerate(self.NmlNames):
                print "\t -- {F} (Line {S} to {E})".format(F=j,S=LineStart[num]+1,E=LineEnd[num]+1)

        #Now make namelist objects for each namelist
        self.Namelists=[]
        for num,name in enumerate(self.NmlNames):
            #Note here we don't pass the last line, usually containing the namelist end /
            self.Namelists.append(FortranNamelist(Lines=Lines[LineStart[num]:LineEnd[num]]))


        #Align the namelists
        self._AlignAll()

        if DEBUG:
            print self

        #Done
        return

    def __str__(self):
        """What should be printed"""
        #First update object
        self._Update()

        Str=[]
        for j in self.Namelists: 
            Str.append(j.__str__())
            Str.append("\n")
        return "\n".join(Str)

    def _AlignAll(self,KeyIndent=None,EqPad=None,ComIndent=None,LeftIndentKey=None,
                  LeftIndentVal=None):
        """Setup the alignment of each namelist"""
        #Align namelists
        #/First get max lengths
        MaxKeyLen=max(map(lambda x:x.MaxKeyLen,self.Namelists))
        MaxValLen=max(map(lambda x:x.MaxValLen,self.Namelists))

        #/Now set these values in all namelists
        jnk=map(lambda x:x._AlignKeyVals(MaxKeyLen=MaxKeyLen,MaxValLen=MaxValLen,
                                         KeyIndent=KeyIndent,EqPad=EqPad,
                                         ComIndent=ComIndent,LeftIndentKey=LeftIndentKey,
                                         LeftIndentVal=LeftIndentVal),self.Namelists)

        return

    def _Update(self):
        """Routine to run on object update.""" 
        #Update children
        jnk=map(lambda x:x._Update(),self.Namelists)

        #Update alignment
        self._AlignAll()
       
    def AddNml(self,Nml=None):
        """A function to add a namelist to a fortran file object"""
        if Nml is None:
            print "ERROR: Must pass in a namelist object."""
            return

        #Append data
        self.NmlNames.append(Nml.Name)
        self.NumNml+=1
        self.Namelists.append(Nml)

        #Update
        self._Update()

        return

    def HasNml(self,Name=None,Count=False,Matches=False):
        """Check if we have at least one namelist with the passed name."""
        if Name is None:
            print "ERROR: Have to specify namelist name you're checking."
            return
        
        #Make a list of logicals saying where the namelists have the desired name
        tmp=map(lambda x: Name.lower()==x.lower(),self.NmlNames)
        NmlPresent=any(tmp)
        NmlCount=tmp.count(True)

        #Now return a logical unless Count=True
        if Count:
            Ans=NmlCount
        else:
            Ans=NmlPresent

        #Do we want to return the matches array?
        if Matches:
            Ans=[Ans,tmp]

        #Return
        return Ans

    def DelNml(self,Name=None,Index=0,Warn=False,Pop=False):
        """Remove selected namelist from file object. 
                *) If there are multiple namelists with the same name then can use Index to 
                specify which one to remove. Set index -ve to remove all matches.
                *) If Pop is set to true then return the namelist object, else just remove it."""
        if Name is None:
            print "ERROR: Have to specify the name of the namelist to remove"
            return
        
        #First check if namelist is present
        if not self.HasNml(Name=Name):
            if Warn:
                print "Warning: File doesn't contain '{N}' namelist".format(N=Name)
            return
        
        #Now count how many there are
        tmp=self.HasNml(Name=Name,Count=True,Matches=True)
        NmlCount=tmp[0]
        NmlMatches=tmp[1]

        #Do we need to invoke Count?
        if NmlCount != 1:
            #If count too large just remove last one
            if Index>NmlCount-1:
                if Warn:
                    print "Warning: Index ({C}) > number of matching namelists ({N}) --> Removing last".format(
                        C=Index,N=NmlCount-1)
                Index=NmlCount-1
        
        #Make a list index lookup type thing
        nind=range(NmlMatches.__len__())
        #Now only get the indices where NmlMatches is true
        nind=[x[1] for x in zip(NmlMatches,nind) if x[0]]

        #Now use pop to remove the various list elements
        #If Index is less than zero then do a re
        if Index<0:
            #Note here we iteratively remove the first matching namelist
            Ans=[self.DelNml(Name=Name,Index=0,Warn=Warn,Pop=Pop) for x in xrange(NmlCount)]
        else:
            jnk=self.NmlNames.pop(nind[Index])
            self.NumNml-=1
            Ans=self.Namelists.pop(nind[Index])

        
        #Update
        self._Update()

        #Return
        if Pop:
            return Ans
        else:
            return

    def PopNml(self,Name=None,Index=0,Warn=False):
        """Remove namelist from file and return removed namelist object."""
        return self.DelNml(Name=Name,Index=Index,Warn=Warn,Pop=True)

    def write(self,Filename=None,Overwrite=False):
        """Write the namelist to a file."""
        if Filename is None:
            print "ERROR: Must pass Filename to write"
            return

        #Check if the file exists
        if os.path.exists(Filename):
            if Overwrite:
                print "Warning: Overwriting file : {F}".format(F=Filename)
            else:
                print "Error: File '{F}' exists, considering setting Overwrite=True".format(F=Filename)
                return
        
        #Open file to write and write lines
        try:
            fil=open(Filename,'w')
        except:
            raise(IOError("Problem during file open."))
        try:
            fil.writelines(self.__str__())
        except:
            raise(IOError("Problem during file write."))
        finally:
            fil.close()

        return

    def GetDict(self):
        """A function to return a dictionary representation of the namelist file."""
        fil_dict={}
        for num,Nml in enumerate(self.Namelists):
            #Have to guard against multiple namelists with the same name
            if self.NmlNames[num] in fil_dict.keys():
                fil_dict[self.NmlNames[num]].append(Nml._AsDict())
            else:
                fil_dict[self.NmlNames[num]]=[Nml._AsDict()]
        return fil_dict

class FortranNamelist:
    """A class representing a fortran namelist."""
    def __init__(self,Lines=None,Name=None):
        #Make empty objects
        self.Name=Name
        self.Keys=[]
        self.Vals=[]
        self.Comments=[]
        self.Lines=[]
        self.PrintLines=[]
        self.KeyVal=[]
        self.MaxKeyLen=0
        self.MaxValLen=0

        #If no lines passed then just make empty objects
        if Lines is None:
            return
        
        #Store raw lines
        self.Lines=Lines

        #Go through lines and remove blank lines, otherwise split into
        #key, value and comment sections
        for Line in self.Lines:
            if Line.strip()=='':
                pass
            else:
                #Add this to the printing lines list
                self.PrintLines.append(Line)

                #Is it a start? if so then get the namelist name
                tmp=_NmlStartReg.match(Line)
                if tmp is not None:
                    self.Name=tmp.groups()[0].strip()
                    continue
                
                #Else it's probably a key val line
                tmp=_KeyValSplit.search(Line)
                if tmp:
                    Key,Val,Com=tmp.groups()
                    if Key: Key=Key.strip()
                    if Val: Val=Val.strip()
                    if Com: Com=Com.strip()
                    self.KeyVal.append(FortranKeyVal(Key=Key,Val=Val,Com=Com))
                    self.Keys.append(Key)
                    self.Vals.append(Val)
                    self.Comments.append(Com)
 
        #Get some info
        self.MaxKeyLen=max(map(lambda x: x.KeyLen,self.KeyVal))
        self.MaxValLen=max(map(lambda x: x.ValLen,self.KeyVal))

        return

    def AddKeyVal(self,KeyVal=None):
        """Routine to add a KeyVal object to the current namelist."""
        if KeyVal is None:
            print "ERROR: Must pass KeyVal object."
            return

        #Append data
        self.Keys.append(KeyVal.Key)
        self.Vals.append(KeyVal.Val)
        self.Comments.append(KeyVal.Com)
        self.KeyVal.append(KeyVal)

        #Update
        self._Update()

        return

    def HasKey(self,Name=None,Count=False,Matches=False):
        """Check if we have at least one Key with the passed name."""
        if Name is None:
            print "ERROR: Have to specify Key name you're checking."
            return
        
        #Make a list of logicals saying where the namelists have the desired name
        tmp=map(lambda x: Name.lower()==x.lower(),self.Keys)
        KeyPresent=any(tmp)
        KeyCount=tmp.count(True) #Should always be 0 or 1

        #Now return a logical unless Count=True
        if Count:
            Ans=KeyCount
        else:
            Ans=KeyPresent

        #Do we want to return the matches array?
        if Matches:
            Ans=[Ans,tmp]

        #Return
        return Ans

    def DelKey(self,Name=None,Index=0,Warn=False,Pop=False):
        """Remove selected key from file object. 
                *) If there are multiple keys with the same name (THERE SHOULDN'T BE!) then can use Index to 
                specify which one to remove. Set index -ve to remove all matches.
                *) If Pop is set to true then return the KeyVal object, else just remove it."""
        if Name is None:
            print "ERROR: Have to specify the name of the key to remove"
            return
        
        #First check if namelist is present
        if not self.HasKey(Name=Name):
            if Warn:
                print "Warning: Namelist doesn't contain '{N}' key".format(N=Name)
            return
        
        #Now count how many there are
        tmp=self.HasKey(Name=Name,Count=True,Matches=True)
        KeyCount=tmp[0]
        KeyMatches=tmp[1]

        #Do we need to invoke Count?
        if KeyCount != 1:
            #If count too large just remove last one
            if Index>KeyCount-1:
                if Warn:
                    print "Warning: Index ({C}) > number of matching keys ({N}) --> Removing last".format(
                        C=Index,N=KeyCount-1)
                Index=KeyCount-1
        
        #Make a list index lookup type thing
        nind=range(KeyMatches.__len__())
        #Now only get the indices where KeyMatches is true
        nind=[x[1] for x in zip(KeyMatches,nind) if x[0]]

        #Now use pop to remove the various list elements
        #If Index is less than zero then do a re
        if Index<0:
            #Note here we iteratively remove the first matching namelist
            Ans=[self.DelKey(Name=Name,Index=0,Warn=Warn,Pop=Pop) for x in xrange(KeyCount)]
        else:
            jnk=self.Keys.pop(nind[Index])
            jnk=self.Vals.pop(nind[Index])
            jnk=self.Comments.pop(nind[Index])
            Ans=self.KeyVal.pop(nind[Index])
        
        #Update
        self._Update()

        #Return
        if Pop:
            return Ans
        else:
            return

    def PopKey(self,Name=None,Index=0,Warn=False):
        """Remove KeyVal from file and return removed KeyVal object."""
        return self.DelKey(Name=Name,Index=Index,Warn=Warn,Pop=True)

    def _Update(self):
        """A function to call to update object"""
        #Update children
        jnk=map(lambda x:x._Update(),self.KeyVal)

        #Update alignment
        self.MaxKeyLen=max(map(lambda x: x.KeyLen,self.KeyVal))
        self.MaxValLen=max(map(lambda x: x.ValLen,self.KeyVal))

        #Update allignments
        self._AlignKeyVals()

    def _AlignKeyVals(self,MaxKeyLen=None,MaxValLen=None,KeyIndent=None,
                      EqPad=None,ComIndent=None,LeftIndentKey=None,
                      LeftIndentVal=None):
        """Align all the key-val pairs based on namelist settings."""
        #Do some formatting stuff
        if MaxKeyLen is None:
            if self.MaxKeyLen >0:
                MaxKeyLen=self.MaxKeyLen
            else:
                MaxKeyLen=max(map(lambda x: x.KeyLen,self.KeyVal))                
        if MaxValLen is None:
            if self.MaxValLen >0:
                MaxValLen=self.MaxValLen
            else:
                MaxValLen=max(map(lambda x: x.ValLen,self.KeyVal))

        #Store new values
        self.MaxKeyLen=MaxKeyLen
        self.MaxValLen=MaxValLen

        #Set alignment parameters
        for j in self.KeyVal:
            j._SetAlignment(MaxKeyLen=MaxKeyLen,MaxValLen=MaxValLen,
                            KeyIndent=KeyIndent,EqPad=EqPad,
                            ComIndent=ComIndent,LeftIndentKey=LeftIndentKey,
                            LeftIndentVal=LeftIndentVal)

    def __str__(self):
        """What to print"""
        Str=[]
        Str.append("&{NM}".format(NM=self.Name))
        for j in self.KeyVal: Str.append(j.__str__())
        Str.append("/")
        return "\n".join(Str)

    def _AsDict(self):
        """A function to return a dictionary representation of the namelist."""
        nml_dict={}
        for KV in self.KeyVal:
            nml_dict[KV.Key]=KV.ValObj
        return nml_dict

class FortranKeyVal:
    """A class to represent a key-val-comment line."""
    def __init__(self,Key=None,Val=None,Com=None):
        #Store values
        self.Key=Key
        self.Val=Val
        self.Com=Com
        self.CommentLine=False
        self.BlankLine=False

        #Check comment starts with ! if not blank
        if self.Com:
            if self.Com != "":
                if not self.Com.startswith("!"):
                    self.Com="!"+self.Com

        #Do some checks
        if (not self.Key is None and self.Val is None):
            raise(RuntimeError("Key {K} is specified but Val is None.".format(K=self.Key)))
        if (self.Key is None and not self.Val is None):
            raise(RuntimeError("Val {K} is specified but Key is None.".format(K=self.Key)))
        
        if self.Key is None and self.Val is None:
            if not self.Com is None:
                self.CommentLine=True
            else:
                self.BlankLine=True

        #Now do some trimming
        if self.Key is not None:
            self.Key=self.Key.strip()
        if self.Val is not None:
            self.Val=self.Val.strip()
        if self.Com is not None:
            self.Com=self.Com.strip()

        #Make a key object
        if self.Key:
            self.KeyObj=FortranKey(self.Key)
            self.KeyLen=self.KeyObj.StrLen
        else:
            self.KeyObj=None
            self.KeyLen=0

        #Make a value object
        if self.Val:
            self.ValObj=FortranVal(self.Val)
            self.ValLen=self.ValObj.StrLen
        else:
            self.ValObj=None
            self.ValLen=0

        #Make a com object
        if self.Com:
            self.ComObj=FortranCom(self.Com)
            self.ComLen=self.ComObj.StrLen
        else:
            self.ComObj=None
            self.ComLen=0

        #Some initial formatting
        self.KeyIndent=2
        self.EqPad=1
        self.EqIndent=self.EqPad
        self.ValIndent=1
        self.ComIndent=1
        self.LeftIndentKey=True
        self.LeftIndentVal=False

        return

    def _SetAlignment(self,MaxKeyLen=None,MaxValLen=None,EqPad=None,KeyIndent=None,
                      ComIndent=None,LeftIndentKey=None,LeftIndentVal=None):
        """Sets the alignment of fields for printing."""
        if not EqPad is None:
            self.EqPad=EqPad
        if not KeyIndent is None:
            self.KeyIndent=KeyIndent
        if not ComIndent is None:
            self.ComIndent=ComIndent
        if not LeftIndentKey is None:
            self.LeftIndentKey=LeftIndentKey
        if not LeftIndentVal is None:
            self.LeftIndentVal=LeftIndentVal

        #How much space do we need to add to the end of Key
        #to make it line up?
        self.EqIndent=MaxKeyLen-self.KeyLen+self.EqPad
        
        #How much space do we need to add to the start of val
        #to make it line up?
        self.ValIndent=MaxValLen-self.ValLen+self.EqPad

        return

    def __str__(self):
        """What do we print"""
        if self.BlankLine:
            return

        Prt=""
        
        #Get alignment strings

        if self.LeftIndentKey:
            EI=" "*(self.EqIndent)
            EIR=""
            KI=" "*self.KeyIndent
            KIR=""            
        else:
            EI=""
            EIR=" "*(self.EqIndent)
            KI=""
            KIR=" "*self.KeyIndent

        if self.LeftIndentVal:
            VI=" "*self.ValIndent
            VIR=""
            CIR=""
            CI=" "*self.ComIndent
        else:
            VI=""
            VIR=" "*(self.ValIndent)
            CIR=" "*self.ComIndent
            CI=""

        if self.Key:
            Prt=Prt+"{Ki}{Eir}{K}{Ei}{Kir}={Vir}{Ci}{V}{Vi}{Cir}"
        
        if self.Com:
            Prt=Prt+"{C}"

        return Prt.format(K=self.Key,V=self.ValObj.__str__(),C=self.Com,
                          Ki=KI,Kir=KIR,Ei=EI,Vi=VI,Ci=CI,Vir=VIR,Eir=EIR,
                          Cir=CIR)


    def _Update(self):
        """Update the object"""
        if self.Key:
            self.KeyObj._Update()
            self.KeyLen=self.KeyObj._GetStrLen()
        if self.Val:
            self.ValObj._Update()
            self.ValLen=self.ValObj._GetStrLen()
        if self.Com:
            self.ComObj._Update()
            self.ComLen=self.ComObj._GetStrLen()


class FortranKey:
    """A class to look after keys."""
    def __init__(self,KeyString=None):
        #Exit if not passed KeyString
        if KeyString is None:
            raise(RuntimeError("Tried to initialise a FortranKey object with None, should pass string"))

        self.Key=KeyString
        self.KeyString=KeyString
        self.StrLen=self._GetStrLen()

    def _Update(self):
        """Update the object"""
        self.StrLen=self._GetStrLen()

    def _GetStrLen(self):
        """Return the length of the string representation of object."""
        return self.__str__().__len__()
    
    def __str__(self):
        """What do we print"""
        return self.KeyString


class FortranCom:
    """A class to look after comments."""
    def __init__(self,ComString=None):
        #Exit if not passed ComString
        if ComString is None:
            raise(RuntimeError("Tried to initialise a FortranCom object with None, should pass string"))

        self.Com=ComString
        self.ComString=ComString
        self.StrLen=self._GetStrLen()


    def _Update(self):
        """Update the object"""
        self.StrLen=self._GetStrLen()

    def _GetStrLen(self):
        """Return the length of the string representation of object."""
        return self.__str__().__len__()
    
    def __str__(self):
        """What do we print"""
        return self.ComString

class FortranVal:
    """A class to look after values."""
    def __init__(self,ValString=None):
        #Exit if not passed ValString
        if ValString is None:
            raise(RuntimeError("Tried to initialise a FortranVal object with None, should pass string"))

        self.IsArray=False

        #Now we basically go through a bunch of regex in order to see what sort of data we have
        #and then do the appropriate conversion
        if _Array.match(ValString):
            #If we have an array then loop through and make a FortranVal object for each
            self.Val=[]
            self.Type=[]
            self.ValString=''
            self.IsArray=True
            for j in ValString.split(","):
                self.Val.append(FortranVal(ValString=j.strip()))
                self.ValString=self.ValString+j.strip()+","
                self.Type.append(self.Val[-1].Type)
            #Now convert to an actual array if all are of the same type
            #(as they should be)
            if all(map(lambda x: x == self.Type[0],self.Type)):
                try:
                    self.Val=np.array(self.Val)
                    self.Type=self.Type[0]
                except:
                    pass

        elif _True.match(ValString):
            self.Val=True
            self.ValString=".TRUE."
            self.Type="logical"
        elif _False.match(ValString):
            self.Val=False
            self.ValString=".FALSE."
            self.Type="logical"
        elif _String.match(ValString):
            self.Val=ValString
            self.ValString=ValString
            self.Type="string"
        elif _Complex.match(ValString):
            tmp=_Complex.match(ValString)
            try:
                self.Val=np.complex(tmp.groups()[0],tmp.groups()[1])
                self.Type="complex"
            except:
                print "Warning: No numpy available so can't make complex variable."
                self.Val=ValString
                self.Type="string"
            self.ValString=ValString
        elif _Number.match(ValString):
            self.ValString=ValString
            if _Int.match(ValString):
                self.Val=int(ValString)
                self.Type="integer"
            else:
                try:
                    self.Val=np.float(ValString.replace("d","e").replace("D","e"))
                    self.Type="real"
                except:
                    print "Warning: No numpy available so can't make real variable (yet)."
                    self.Val=ValString
                    self.Type="string"
        else:
            raise(RuntimeError("Unknow type for ValString {V}".format(V=ValString)))


        #Get the string length
        self.StrLen=self._GetStrLen()

    def _Update(self):
        """Update the object"""
        self.StrLen=self._GetStrLen()

    def _GetStrLen(self):
        """Return the length of the string representation of object."""
        return self.__str__().__len__()

    def __str__(self):
        """What do we print"""
        try:
            if self.IsArray:
                return ", ".join(map(str,self.Val))
            else:
                return self.Val.__str__()
        except:
            return self.ValString
