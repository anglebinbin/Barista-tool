import os
import re

from backend.barista.utils.settings import applicationQSetting

from backend.barista.utils.logger import Log

class Singleton(type):
    """This metaclass is used to provide the singleton pattern in a generic way.

    See http://stackoverflow.com/a/6798042 for source and further explanation.
    TODO outsource this class to use the same pattern in the complete project?
    """
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class CaffeProtoParser:
    """This class parses the caffe.proto file.

    This is different from what is done in other files of this package, as this is the first time we really parse the
    text file itself on our own. Other methods rely on meta data provided after(!) parsing/compiling that file.
    """
    __metaclass__ = Singleton

    def __init__(self, replaceLineBreaks=True):
        """

        replaceLineBreaks:
            If True, all line breaks will be replaced by spaces. This is the default behavior as most line breaks are only
            caused by the limited code width rather than for semantic reasons.
            Anyway, there are also some parameter descriptions using linebreaks on purpose (e.g. lr_policy).
            (This does not affect cases in which there is an empty comment line. The latter will be kept anyway.)
        """

        self._replaceLineBreaks = replaceLineBreaks
        self._fileContent = self._readFile()
        self._fieldDescriptions, self._messageDescriptions = self._parseComments()



    def _readFile(self):
        """Read the content of the caffe.proto file."""
        import backend.barista.caffe_versions as caffeVersions
        # get path to caffe.proto file
        caffeProtoFilePath = caffeVersions.getAvailableVersions()[0].getProtopath()

        if os.path.isfile(caffeProtoFilePath):
            # open caffe.proto file
            with open(caffeProtoFilePath) as f:
                # read complete file at once
                content = f.read()
        else:
            callerId = Log.getCallerId("parameter_descriptions")
            Log.error("ERROR: Unable to load caffe.proto file. Parameter descriptions and deprecated flags "
                      "will be left empty. Did you configure the environment variable CAFFE_ROOT?", callerId)
            content = ""

        return content

    def _parseComments(self):
        """Parse all parameter descriptions provided in the C-style comments.

        Results will be provided by the fieldDescriptions() and messageDescriptions() methods.
        """

        # our result cache
        fieldDescr = {}
        msgDescr = {}

        # get all defined messages and their content to be able grouping their parameters
        # regex inside of outer msg brackets:
        #  repeat (any chars except brackets) or (opening bracket + any chars except brackets + closing brackets)
        msgBlocks = re.findall('((//[^\n]*\n)*)message\s*(\w+)\s*\{('  # begin of message definition
                                '([^\{\}]|(\{[^\{\}]*\}))*'
                                ')\}', self._fileContent)  # end of message definition

        for block in msgBlocks:

            # only some of the groups are relevant. ignore the rest.
            msgName = block[2]
            msgContent = block[3]

            # first of all: get the comment right above the message itself. not the ones included.
            msgCommentLines = block[0].splitlines()
            msgComment = ""
            for line in msgCommentLines:
                msgComment = self._proccessCommentLine(line, msgComment)
            if len(msgComment) > 0:
                msgDescr[msgName] = self._finalizeComment(msgComment)

            # collect all parameters of this message, before adding them to the global result
            msgParams = {}

            # parse line by line of the message's content and add it to either a comment, parameter, or nothing
            msgLines = msgContent.splitlines()
            currComment = ""
            for line in msgLines:

                # check whether this is a comment line or a parameter line
                # (if a comment has been added next to a param definition, it might be both)
                isComment = re.search(r'.*//\s*(.*)\s*', line) is not None  # do not restrict to leading whitespaces!
                nonEnumParamMatch = re.search(r'\s*(repeated|optional|required)\s*(\w+)\s*(\w+)\s*=', line)
                enumParamMatch = re.search(r'\s*enum\s*(\w+)\s*\{', line)
                isParam = nonEnumParamMatch is not None or enumParamMatch is not None

                # if this is a comment line..
                if isComment:

                    # add line to current comment
                    currComment = self._proccessCommentLine(line, currComment)

                # if the last lines have build a comment and this line contains a new parameter definition..
                if len(currComment) > 0 and isParam:

                    # add the current parameter to the list of the current message
                    if nonEnumParamMatch is not None:
                        paramName = nonEnumParamMatch.group(3)
                    else:
                        paramName = enumParamMatch.group(1)
                    msgParams[paramName] = self._finalizeComment(currComment)

                # reset current comment, if this line isn't one anymore or if it is a inline-comment that belongs
                # to the parameter in the same line => this param was already processed
                if not isComment or isParam:
                    currComment = ""

            # if any parameter descriptions have been found for this message, add it to the global result
            if len(msgParams) > 0:
                fieldDescr[msgName] = msgParams

        return fieldDescr, msgDescr

    def _proccessCommentLine(self, line, currComment):
        """Process line as a comment line and append the result to currComment."""

        # the content of this line without everything which comes before the comment slashes
        commentReducible = re.search(r'.*//\s*(.*)\s*', line)

        if commentReducible is not None:
            lineContent = commentReducible.group(1)
        else:  # might be empty or reduced already
            lineContent = line

        # check whether this comment line does only contain whitespaces
        isNotEmpty = re.search(r'\S+', lineContent)

        # recreate linebreaks or replace them with spaces
        # (don't add anything at the beginning or if the last char is a newline, which might happen in all configs)
        if len(currComment) > 0 and currComment[-1] != "\n":
            if isNotEmpty is not None:
                if self._replaceLineBreaks:
                    currComment += " "
                else:
                    currComment += "\n"
            else:
                # if this is an empty comment line, add an empty line to the full comment, too.
                currComment += "\n\n"

        # add text of current line to current comment
        if isNotEmpty is not None:
            currComment += lineContent

        return currComment

    def _finalizeComment(self, comment):
        """Call this method for each comment after each line has been processed by _proccessCommentLine()."""

        # remove multiple spaces following each other
        while "  " in comment:
            comment = comment.replace("  ", " ")

        # unify descriptions: add a "." at the end of each non-empty comment.
        if len(comment) > 0 and comment[-1] != ".":
            comment += "."

        # capitalize first letter
        comment = comment.capitalize()

        return comment

    def fieldDescriptions(self):
        """Get all descriptions provided in the caffe.proto file's comments, that belong to a field inside of a message.

        Returned value is a dictionary of dictionaries. Keys of the first dimension are names of messages,
        e.g. 'AccuracyParameter'. Keys of the second dimension are parameter names of those messages, such as 'top_k'.
        Finally, each of those keys is connected to a string containing the actual description. If a message/parameter
        does not have any descriptions, there won't be a dictionary entry for that element at all.
        """
        return self._fieldDescriptions

    def messageDescriptions(self):
        """Get all descriptions provided in the caffe.proto file's comments, that belong to a message itself.

        The returned value is a dictionary. Keys are message names and values their descriptions as strings.
        """
        return self._messageDescriptions

    def description(self, msgName, fieldName=None, fieldMsgDefault=None):
        """Get a single description for either a field of a message or a message itself.

        fieldName: If None, the message description for msgName will be returned.
            Otherwise, the description for fieldName of msgName.

        fieldMsgDefault: If field is also a message, the general message description of
            messageDescriptions()[fieldMsgDefault] will be used as a default value for field.
        """

        description = ""

        if fieldName is None:  # message description
            if msgName in self.messageDescriptions():
                description = self.messageDescriptions()[msgName]
        else:  # field description
            if msgName in self.fieldDescriptions() and fieldName in self.fieldDescriptions()[msgName]:
                description = self.fieldDescriptions()[msgName][fieldName]
            elif fieldMsgDefault is not None and fieldMsgDefault in self.messageDescriptions():
                # field description based on message description
                description = self.messageDescriptions()[fieldMsgDefault]

        return description
