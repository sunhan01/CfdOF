# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2016 - Qingfeng Xia <qingfeng.xia iesensor.com>         *
# *   Copyright (c) 2017 - Johan Heyns (CSIR) <jheyns@csir.co.za>           *
# *   Copyright (c) 2017 - Oliver Oxtoby (CSIR) <ooxtoby@csir.co.za>        *
# *   Copyright (c) 2017 - Alfred Bogaers (CSIR) <abogaers@csir.co.za>      *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

from __future__ import print_function
from utility import *
import subprocess
import platform
_debug = True


class BasicBuilder(object):
    """ This class to construct the OpenFOAM file structure. """
    def __init__(self,
                 casePath,
                 installationPath,
                 solverSettings,
                 physicsModel,
                 initialConditions,
                 templatePath,
                 solverName=None,
                 fluidProperties={'name':'air'},
                 boundarySettings=[],
                 internalFields={},
                 porousZoneSettings=[]):

        if casePath[0] == "~":
            casePath = os.path.expanduser(casePath)
        self._casePath = os.path.abspath(casePath)
        self._installationPath = installationPath
        self._solverSettings = solverSettings
        self._physicsModel = physicsModel
        self._initialConditions = initialConditions
        self._solverName = solverName
        # NOTE: Code depreciated (JH) 06/02/2017
        # if solverNameExternal:
        #     self._solverName = solverNameExternal
        # else:
        #     self._solverName = self.getSolverName()
        self._templatePath = templatePath
        self._solverCreatedVariables = self.getSolverCreatedVariables()
        self._fluidProperties = fluidProperties
        self._boundarySettings = boundarySettings
        self._internalFields = internalFields
        self._porousZoneSettings = porousZoneSettings
        self._edit_process = None

    def setInstallationPath(self):
        setFoamDir(self._installationPath)

    def createCase(self):
        """ Remove existing folder and create a new folder. """
        # NOTE: Code depreciated (JH) 08/02/17 - Only building from template
        # if self._templatePath:
        createCaseFromTemplate(self._casePath, os.path.join(self._templatePath, self._solverName))
        # NOTE: Code depreciated (JH) 08/02/17 - Only building from template
        # else:
        #     createCaseFromScratch(self._casePath, self._solverName)
        self._createInitVariables()

    def pre_build_check(self):
        """ Run pre-build checks. """
        print("Run pre-build check.")
        if self._solverSettings['parallel']:
            if self._solverSettings['parallelCores'] < 2:
                self._solverSettings['parallelCores'] = 2

    def build(self):
        #if not rebuilding:
        #    createCaseFromTemplate(self._casePath, self._templatePath)

        # Should be repeated on rebuild after settings change
        self.updateTemplateControlDict()  # Updates the solver time step controls
        self.modifySolutionResidualTolerance()  # Updates the solver convergence tolerance for p and U fields.
        createRunScript(self._casePath, self._templatePath,
                        self._initialConditions["PotentialFoam"],
                        self._solverSettings['parallel'],
                        self._solverName,
                        self._solverSettings['parallelCores'],
                        self._porousZoneSettings,
                        self.bafflesPresent())

        self.setupFluidProperties()
        self.setupTurbulenceProperties()

        self.setupBoundaryConditions()
        if len(self._porousZoneSettings) > 0:
            self.setupTopoSetDict()
            self.setupFVOptions()
        if self.bafflesPresent():
            self.setupCreateBafflesDict()
        self.setupInternalFields()

        # NOTE: Code depreciated (AB) 20/01/2017
        # setupSolverControl currently does not do anything as all relevant solver control files are copied from a best
        # practices directory. controlDict is already copied and runtime information is subsequently modify.
        # if self._solverSettings['transient']:
        #     self.setupSolverControl()
        if self._solverSettings['parallel']:
            self.setupParallelSettings()
        # NOTE: Code depreciated (JH) 06/02/2017
        # if self._solverSettings['buoyant']:
        #     self.writeGravityProperties()
        # if self._solverSettings['dynamicMeshing']:
        #     self.setupDynamicMeshingProperties()
        # self.setupSolverControl() # residual, relaxfactor refValue, refCell etc

        # Move mesh files, after being edited, to polyMesh.org
        movePolyMesh(self._casePath)

    def setupMesh(self, updated_mesh_path, scale):
        if os.path.exists(updated_mesh_path):
            convertMesh(self._casePath, updated_mesh_path, scale)

    # NOTE: Code depreciated (JH) 06/02/2017
    # def updateMesh(self, updated_mesh_path, scale):
    #     print ('updateMesh ........ ')
    #     casePath = self._casePath
    #     shutil.remove(casePath + os.path.sep + "constant" + os.path.sep + 'polyMesh')
    #     self.setupMesh(updated_mesh_path, scale)

    def post_build_check(self):
        """ Run post-build checks. """
        print ("Run post-build check.")
        case = self._casePath
        # NOTE: Code depreciated (JH) 06/02/2017
        # if self._solverSettings['dynamicMeshing']:
        #     if not os.path.exists(case + os.path.sep + 'constant/dynamicMeshDict'):
        #         return "Error: 'constant/dynamicMeshDict' is not existent while dynamcMeshing opiton is selected"
        #     if not os.path.exists(case + os.path.sep + '0/pointDisplacement'):
        #         return "Error: '0/pointDisplacement' is not existent while dynamcMeshing opiton is selected"
        # ''' NOTE: Code depreciated - 25/02/2017 (JAH) '''
        # if self._solverSettings['porous']:
        #     return 'Error: Porous flow need temperatuare field, use ThermalBuilder'
        if self._solverSettings['parallel']:
            if not os.path.exists(case + os.path.sep + 'constant/decomposeParDict'):
                return "Warning: File 'constant/decomposeParDict' is not available for parallel analysis."
        # NOTE: Code depreciated (JH) 06/02/2017
        # if self._solverSettings['buoyant']:
        #     if not os.path.exists(case + os.path.sep + 'constant/g'):
        #         return "Error: 'constant/g' is not existent while buoyant opiton is selected"
        # paired boundary check: cyclic, porous, etc

    # NOTE: Code depreciated (JH) 06/02/2017
    # def summarize(self):
    #     """ Provide a summary the case setup. """
    #     print("================= case summary ==================\n")
    #     print("Solver name: {}".format(self._solverName))
    #     print("Solver template: {}".format(self._templatePath))
    #     print("Solver case path: {}".format(self._casePath))
    #     self._summarizeInternalFields()
    #     print("Defined mesh boundary names: {}".format(listBoundaryNames(self._casePath)))
    #     print("Boundary conditions setup:")
    #     for bc in self._boundarySettings:
    #         print(bc)
    #     if self._solverSettings['transient']:
    #         print("Transient settings:")
    #         print(self._timeStepSettings) # Get for solverSet
    #     # cmdline = self.getSolverCmd()
    #     # foamJob <solver> & foamLog
    #     print("Please run the command in new terminal: \n" + cmdline)
    #
    # NOTE: Code depreciated (JH) 06/02/2017
    # def _summarizeInternalFields(self):
    #     print("Solver created fields are initialized with value:\n")
    #     for var in self._solverCreatedVariables:
    #         f = ParsedParameterFile(self._casePath + os.path.sep + "0" + os.path.sep + var)
    #         print("    {}:      {}".format(var, f['internalField']))
    #
    # NOTE: Code depreciated (JH) 06/02/2017
    # def getSolverCmd(self):
    #     # casePath may need translate for OpenFOAM on windows
    #     log = "{}/log.{}".format(self._casePath, self._solverName)
    #     case = translatePath(self._casePath)
    #     if self._solverSettings['parallel']:
    #         cmd = "decomposePar -case {}  && ".format(case)
    #         nCores = multiprocessing.cpu_count()
    #         cmd += "mpirun -np {} {} -case {} > {}".format(nCores, self._solverName, case, log)
    #     else:
    #         cmd = "{} -case {} > {}".format(self._solverName, case, log)
    #     return cmd

    def editCase(self):
        """ Open case folder externally in file browser. """
        path = self._casePath
        if platform.system() == 'MacOS':
            self._edit_process = subprocess.Popen(['open', '--', path])
        elif platform.system() == 'Linux':
            # TODO: For whatever reason this only seems to respond when called twice on my system...how universal is this?
            self._edit_process = subprocess.Popen(['xdg-open', path])
        elif platform.system() == 'Windows':
            self._edit_process = subprocess.Popen(['explorer', path])

    # NOTE: Update code when VTK is revived (JH)
    # def exportResult(self):
    #     """  Export to VTK format (ascii or binary format) and allow user to directly view results in FC. """
    #     if self._solverSettings['parallel']:
    #         runFoamApplication(['reconstructPar'],  self._casePath)
    #     if os.path.exists(self._casePath + os.path.sep + "VTK"):
    #         shutil.rmtree(self._casePath + os.path.sep + "VTK")
    #     # pointSetName = 'wholeDomain'
    #     # createRawFoamFile(self._casePath, 'system', 'topoSetDict',
    #     #                   getTopoSetDictTemplate(pointSetName, 'pointSet', boundingBox))
    #     # runFoamCommand(['topoSet', '-case', self._casePath, '-latestTime'])
    #     # runFoamCommand(['foamToVTK', '-case', self._casePath, '-latestTime', '-pointSet', pointSetName])
    #     runFoamApplication(['foamToVTK', '-latestTime'], self._casePath)
    #     # search for *.vtk
    #     import glob
    #     vtk_files = glob.glob(self._casePath + os.path.sep + "VTK" + os.path.sep + "*.vtk")
    #     if len(vtk_files) >= 1:
    #         print("only one file name with full path is expected for the result vtk file")
    #         return vtk_files[-1]

    def createParaviewScript(self, module_path):
        """ Create python script for Paraview. """
        fname = os.path.join(self._casePath, "pvScript.py")
        if self._solverSettings['parallel']:
            case_type = "Decomposed Case"
        else:
            case_type = "Reconstructed Case"

        script_head = os.path.join(module_path, "data/defaults/paraview/pvScriptHead.py")
        script_tail = os.path.join(module_path, "data/defaults/paraview/pvScriptTail.py")

        if os.path.exists(fname):
            print("Warning: Overwrite existing pvScript.py script")
        with open(fname, 'w+') as f:  # Delete existing content or create new

            # Insert script head
            with open(script_head, "rb") as infile:
                f.write(infile.read())
            f.write("\n# create a new OpenFOAMReader\n")
            f.write("pfoam = OpenFOAMReader(FileName=r'{}')\n".format(os.path.join(self._casePath, "p.foam")))
            f.write("pfoam.CaseType = '{}'\n\n".format(case_type))

            # Insert script tail
            with open(script_tail, "rb") as infile:
                f.write(infile.read())

            if not os.path.exists(os.path.join(self._casePath, "p.foam")):
                f = open(os.path.join(self._casePath, "p.foam"), 'w')  # mknod not available on Windows
                f.close()

            return fname

    # Solver settings: Update time step and convergence controls

    def updateTemplateControlDict(self):
        modifyControlDictEntries(self._casePath + os.path.sep + "system" + os.path.sep + "controlDict",
                                 "endTime",
                                 self._solverSettings['endTime'])
        modifyControlDictEntries(self._casePath + os.path.sep + "system" + os.path.sep + "controlDict",
                                 "writeInterval",
                                 self._solverSettings['writeInterval'])
        modifyControlDictEntries(self._casePath + os.path.sep + "system" + os.path.sep + "controlDict",
                                 "deltaT",
                                 self._solverSettings['timeStep'])

    def modifySolutionResidualTolerance(self):
        f = ParsedParameterFile(self._casePath + os.path.sep + "system" + os.path.sep + "fvSolution")
        if "Simple" in self._solverName or "simple" in self._solverName:
            f["SIMPLE"]['residualControl']['p'] = self._solverSettings['convergenceCriteria']
            f["SIMPLE"]['residualControl']['U'] = self._solverSettings['convergenceCriteria']
        elif "Pimple" in self._solverName or "pimple" in self._solverName:
            f["PIMPLE"]['residualControl']['p']['tolerance'] = self._solverSettings['convergenceCriteria']
            f["PIMPLE"]['residualControl']['U']['tolerance'] = self._solverSettings['convergenceCriteria']
        else:
            print("Solver not yet supported")
        f.writeFile()

    # NOTE: Code depreciated (JH) 06/02/2017
    # def getSolverName(self):
    #     return _getSolverName(self._solverSettings)
    #
    # NOTE: Code depreciated (JH) 06/02/2017
    # def getFoamTemplate(self):
    #     """
    #     zipped template 'simpleFoam' works with OpenFOAM 3.0+ and 2.x
    #     In case PyFoam can not load the case file as dict
    #     """
    #     solver_name = self._solverName
    #     if self._solverSettings['turbulenceModel'] in LES_turbulence_models:
    #         using_LES = True
    #     else:
    #         using_LES = False
    #
    #     script_path = os.path.dirname(os.path.abspath( __file__ ))
    #     template_path = script_path + os.path.sep + solver_name + "_template_v" + str(getFoamVersion()[0]) + ".zip"
    #     if not os.path.exists(template_path):
    #         if solver_name in _RAS_solver_templates:
    #             template = _RAS_solver_templates[solver_name]
    #         elif using_LES and solver_name in _LES_turbulenceModel_templates:
    #             template = _LES_solver_templates[solver_name]
    #         else:
    #             raise Exception('No tutorial template is found for solver: ' + solver_name)
    #         if template:
    #             return getFoamDir() + os.path.sep + template
    #         else:
    #             raise Exception('No tutorial template is registered for solver: ' + solver_name)
    #     else:
    #         return template_path # case folder zipped with version number

    def getSolverCreatedVariables(self):
        """ Create a list of the required solver variables. """
        # NOTE: Update code when added turbulence back to the code (JH)
        # vars = ['p', 'U'] + getTurbulenceVariables(self._solverSettings)
        vars = ['p', 'U']
        # NOTE: Code depreciated (JH) 06/02/2017
        # if self._solverSettings['buoyant']:
        #     vars.append("p_rgh")
        # if self._solverSettings['dynamicMeshing']:
        #     vars.append("pointDisplacement") #only 6DoF motion solver needs this variable
        return set(vars)

    def _createInitVariables(self):
        """ Add the solver variables to the '0' folder. It is assumed the folder is empty and all variable files
        are to be created from scratch.
        """
        vars = self.getSolverCreatedVariables()
        casePath = self._casePath
        initFolder = casePath + os.path.sep + "0"
        if not os.path.exists(initFolder):
            if _debug:
                print('Warning: Folder \'0\' does not exist, creating a new one.')
            os.makedirs(initFolder)

        if _debug: print("Info: Initialise solver created fields (variables): ", vars)

        for v in vars:
            fname = casePath + os.path.sep + "0" + os.path.sep + v
            lines = ["dimensions  [0 0 0 0 0 0 0];\n", "\n",
                     "internalField uniform 0;\n", "\n",  # Updated in caseBuilder
                     'boundaryField\n', "{\n", "\n", "}\n"]
            if v.split('.')[0] in set(['U', 'pointDisplacement']):
                createRawFoamFile(casePath, '0', v, lines, 'volVectorField')
            elif v.split('.')[0] in set(['p', 'p_rgh', 'T', 'alphat', 'alpha',
                                         'k', 'epsilon', 'omega', 'nut', 'nuSgs', 'nuTilda']):
                createRawFoamFile(casePath, '0', v, lines, 'volScalarField')
            else:
                print("Info: variable {} is left unchanged".format(v))

            f = ParsedParameterFile(fname)
            if v.split('.')[0] == 'U':
                f['dimensions'] = '[0 1 -1 0 0 0 0]'
                f['internalField'] = 'uniform (0 0 0)'
            elif v == 'p' or v == 'p_rgh':
                # if self._solverSettings['compressible']:
                if self._physicsModel['Flow'] == 'Compressible':
                    f['dimensions'] = '[1 -1 -2 0 0 0 0]'  # P [Pa], m-1, kg, s-2
                    f['internalField'] = 'uniform 101000'  # P_rgh for heat transfer P must be > 0
                else:
                    f['dimensions'] = '[0 2 -2 0 0 0 0]'  # P / rho
                    f['internalField'] = 'uniform 0'
            # NOTE: Code depreciated (JH) 06/02/2017
            # elif v == 'pointDisplacement':  # dynamicMeshing 6DoF motion solver needs this var
            #     f['dimensions'] = "[0 1 0 0 0 0 0]"
            #     f['internalField'] = 'uniform (0 0 0)'
            # thermal variable
            elif v.split('.')[0] == 'T':
                f['dimensions'] = "[0 0 0 1 0 0 0]"
                f['internalField'] = "uniform 300"
            elif v.split('.')[0] == 'alphat':  # Thermal turbulence viscosity/diffusivity
                f['dimensions'] = "[1 -1 -1 0 0 0 0]"
                f['internalField'] = 'uniform 0' #
            elif v.split('.')[0] == 'k':
                f['dimensions'] = "[ 0 2 -2 0 0 0 0 ]"
                f['internalField'] = 'uniform 0.00325'
            elif v.split('.')[0] == 'epsilon':
                f['dimensions'] = "[ 0 2 -3 0 0 0 0 ]"
                f['internalField'] = 'uniform 0.000765'
            elif v.split('.')[0] == 'omega':
                f['dimensions'] = "[0 0 -1 0 0 0 0]"  # same unit with Frequency
                f['internalField'] = "uniform 2.6"
            elif v.split('.')[0] == 'nut' or v == 'nuTilda' or v == 'nuSgs':  # mut is needed for openfoam 2.x, foam-ext
                f['dimensions'] = "[0 2 -1 0 0 0 0]"
                f['internalField'] = "uniform 0"
            # NOTE: Code depreciated (JH) 06/02/2017
            # elif v == 'alpha':  # specie fraction
            #     f['dimensions'] = "[0 0 0 0 0 0 0]"
            #     f['internalField'] = 'uniform 0'  # non dimensional (0~1)
            else:
                print("variable {} is not recognized and dimension is left unchanged".format(v))

            f.writeFile()

    @property
    def solverSettings(self):
        return self._solverSettings

    # NOTE: Code depreciated (JH) 06/02/2017
    # def setupSolverSettings(self, settings):
    #     if settings and isinstance(value, dict):
    #         self._solverSettings = settings
    #         self._solverName = getSolverName(self._solverSettings)
    #         self._solverCreatedVariables = getSolverCreatedVariables(self._solverSettings)

    # @property
    # def parallelSettings(self):
    #     return self._parallelSettings

    def setupParallelSettings(self):
        """ Create the parallel dictionary file 'decomposeParDict' """
        f = self._casePath + os.path.sep + 'decomposeParDict'
        createRawFoamFile(self._casePath, 'system', 'decomposeParDict',
                          getDecomposeParDictTemplate(self._solverSettings['parallelCores'], 'scotch'))

    @property
    def fluidProperties(self):
        return self._fluidProperties

    @fluidProperties.setter
    def fluidProperties(self, value):
        if value and isinstance(value, dict):
            self._fluidProperties = value
        else:
            print("set a invalid fluid property, null or not dict")
        if _debug:
            print(self._fluidProperties)

    def setupFluidProperties(self):
        """ Set density and viscosity in transport properties. """
        case = self._casePath
        # solver_settings = self._solverSettings
        # assert solver_settings['compressible'] == False
        assert self._physicsModel['Flow'] == 'Incompressible'

        lines = ['transportModel  Newtonian;\n']
        # NOTE: Code depreciated (JH) 06/02/2017
        # if solver_settings['nonNewtonian']:
        #     print('Warning: nonNewtonian case setup is not implemented, please edit dict file directly')
        # else:

        for k in self._fluidProperties:
            if k in set(['nu', 'kinematicViscosity']):
                viscosity = self._fluidProperties[k]
                lines.append('nu              nu [ 0 2 -1 0 0 0 0 ] {};\n'.format(viscosity))
            elif k in set(['rho', 'density']):
                density = self._fluidProperties[k]
                lines.append('rho              rho [ -3 1 0 0 0 0 0 ] {};\n'.format(density))
            else:
                print("Warning:unrecoginsed fluid properties: {}".format(k))
        if _debug:
            print("Viscosity settings in constant/transportProperties")
            print(lines)

        createRawFoamFile(case, "constant", "transportProperties", lines)

    # NOTE: Update code when functionality is added (JH) 07/02/2017
    # @property
    # def gravity(self):
    #     # return self._solverSettings['gravity']

    # NOTE: Update code when functionality is added
    # @gravity.setter
    # def setGravityProperties(self, value):
    #     """ Set gravity vector. """
    #     if value and len(value) == 3:
    #         self._solverSettings['gravity'] = value

    # NOTE: Update code when functionality is added (JH) 07/02/2017
    # def writeGravityProperties(self):
    #     """ Set gravity vector. """
    #     value = self._solverSettings['gravity']
    #     lines = ["dimensions    [0 1 -2 0 0 0 0];\n", "value    ({} {} {}); \n".format(value[0], value[1], value[2])]
    #     createRawFoamFile(self._casePath, "constant", "g", lines, "uniformDimensionedVectorField")

    @property
    def internalFields(self):
        return self._internalFields

    @internalFields.setter
    def internalFields(self, fields=None):
        if fields and isinstance(fields, dict):
            self._internalFields = fields  # Mapping type like dict
        else:
            print('Warning: only dict with variable name as key is accepted to init internal fields')

    def setupInternalFields(self, fields=None):
        # support a short name in openfoam dict file like 'T' and long name like 'Temperature'
        if fields and isinstance(fields, dict):
            self.internalFields = fields

        for k in self._internalFields:
            if k.split('.')[0] == 'U': # multiphase has variable name 'U.air'
                var = k
            elif k.split('.')[0] in set(['velocity', 'Velocity']):
                var = k.replace(k.split('.')[0], 'U')
                self._internalFields[var] = self._internalFields[k]
            elif k.lower() in set(['p', 'p_rgh']): # mixture has only one pressure
                var = k
            elif k.lower() in set(['pressure']):
                var = 'p'
                self._internalFields[var] = self._internalFields[k]
            # NOTE: Code depreciated (JH) 07/02/2017
            # elif k == 'pointDisplacement':  # dynamic meshing 6DOF
            #     var = k
            #
            # NOTE: Update code when added turbulence back to the code (JH)
            # Turbulence variables
            # elif k.split('.')[0] in set(['nut', 'turbulenceviscosity', 'turbulenceViscosity', 'TurbulenceViscosity']):
            #     var = k.replace(k.split('.')[0], 'nut')
            #     self._internalFields[var] = self._internalFields[k]
            # elif k.split('.')[0] in set(['k', 'turbulenceEnergy', 'TurbulenceEnergy', 'turbulenceKineticEnergy']):
            #     var = k.replace(k.split('.')[0], 'k')
            #     self._internalFields[var] = self._internalFields[k]
            # elif k.lower() in set(['epsilon', 'turbulencedissipationrate']):
            #     var = 'epsilon'
            # elif k.split('.')[0] == 'omega':
            #     var = k
            # elif k.lower() in set(['omega', 'specificdissipationrate']):
            #     var = 'omega'
            # # thermal flow varaible
            # elif k.split('.')[0] in set(['T', 'temperature', 'Temperature']):
            #     var = k.replace(k.split('.')[0], 'T')
            #     self._internalFields[var] = self._internalFields[k]
            # elif k.lower() in set(['alphat', 'turbulencethermaldiffusivity']):
            #     var = 'alphat'
            # elif k.split('.')[0] == "alphat":
            #     var = k
            # # multiple phase varaible
            # elif k.lower().split('.')[0] == 'alpha':
            #     var = k
            # elif k.lower() in set(['alpha', 'phaseratio']):
            #     var = 'alpha'
            # else:
            #     var = k

            # Update the initial internal field
            value = self._internalFields[var]
            if var in self._solverCreatedVariables:
                f = ParsedParameterFile(self._casePath + "/0/" + var)
                f["internalField"] = formatValue(value)
                f.writeFile()
            else:
                print("Warning: variable:{} is not recognised/created thus ignored in setupInternalFields()".format(k))


    # System settings

    # NOTE: Code depreciated (JH) 08/02/2017
    # @property
    # def timeStepSettings(self):   # Get for solverSet
    #    return self._timeStepSettings

    # @timeStepSettings.setter
    # def timeStepSettings(self, timeStepSettings):
    #     if timeStepSettings:
    #         self._timeStepSettings = timeStepSettings

    # NOTE: Code depreciated (JH) 06/02/2017
    # def setupTimeStepSettings(self, tSettings):
    #     if tSettings:
    #         self.timeStepSettings = tSettings # Get for solverSet
    #     if self._timeStepSettings:
    #         f = ParsedParameterFile(self._casePath + "/system/controlDict")
    #         # f["startTime"] = self._timeStepSettings["startTime"] # Should always be zero
    #         f["endTime"] = self._timeStepSettings["endTime"]  # Get for solverSet
    #         f["deltaT"] = self._timeStepSettings["timeStep"]
    #         f["writeInterval"] = self._timeStepSettings["writeInterval"]
    #         f.writeFile()
    #     else:
    #         print("timeStepSettings is None")
    #
    # NOTE: Code depreciated (JH) 06/02/2017
    # def setupDynamicMeshingProperties(self):
    #     """ must relies on template setup,
    #     also the 'pointDisplacement' boundary need setup
    #     """
    #     pass

    # Solver control

    # NOTE: Code depreciated (AB) 20/01/2017
    # def setupSolverControl(self):
    #     f = ParsedParameterFile(os.path.join(self._casePath, "system", "fvSolution"))

    # NOTE: Code depreciated (JH) 06/02/2017
    # def setupRelaxationFactors(self, pressure_factor=0.1, velocity_factor=0.1, other_factor=0.3):
    #     print ('........................................')
    #     # '.*' apply to all variables
    #     f = ParsedParameterFile(self._casePath + "/system/fvSolution")
    #     f["relaxationFactors"]["fields"] = {} # this `fields` may not exist
    #     f["relaxationFactors"]["fields"]["p"] = pressure_factor
    #     f["relaxationFactors"]["equations"] = {}
    #     f["relaxationFactors"]["equations"]["U"] = velocity_factor
    #     f["relaxationFactors"]["equations"]['"(k|epsilon|omega|nut|f|v2)"'] = other_factor
    #     f["relaxationFactors"]["equations"]['\".*\"'] = other_factor
    #     f.writeFile()

    # NOTE: Code depreciated (JH) 06/02/2017
    # def setupPressureReference(self, pRefValue, pRefCell=0):
    #     f = ParsedParameterFile(self._casePath + "/system/fvSolution")
    #     for algo in _supported_algorithms:
    #         if algo in f:
    #             f[algo]["pRefValue"] = pRefValue
    #             f[algo]["pRefCell"] = pRefCell
    #     f.writeFile()

    # NOTE: Code depreciated (JH) 06/02/2017
    # def setupNonOrthogonalCorrectors(self, nTimes):
    #     ## important for netgen mesh with only tetragal cell to convergent
    #     f = ParsedParameterFile(self._casePath + "/system/fvSolution")
    #     for algo in _supported_algorithms:
    #         if algo in f:
    #             f[algo]['nNonOrthogonalCorrectors'] = nTimes
    #     f.writeFile()

    # NOTE: Code depreciated (JH) 06/02/2017
    # def setupResiduals(self, pResidual, UResidual, other = 0.001):
    #     print ('........................................')
    #     f = ParsedParameterFile(self._casePath + "/system/fvSolution")
    #     for algo in _supported_algorithms:
    #         if algo in f:
    #             f[algo]['residualControl'] = {'p': pResidual, 'U': pResidual, '\".*\"': other}
    #     f.writeFile()

    # NOTE: Code depreciated (JH) 06/02/2017
    # def setupSolverSchemes(self):
    #     """
    #     # add new variable (for diff turbulence model) schemes if abscent in source template
    #     divSchemes
    #     {
    #         default         none;
    #         div(phi,U)      bounded Gauss upwind;
    #         div(phi,T)      bounded Gauss upwind;
    #         div(phi,k)      bounded Gauss upwind;
    #         div(phi,epsilon) bounded Gauss upwind;
    #         div((nuEff*dev2(T(grad(U))))) Gauss linear;
    #     }
    #     """
    #     #f = ParsedParameterFile(self._casePath + "/system/fvSchemes")
    #     pass

    # Boundary conditions

    def writeDefaultBoundaryConditions(self):
        """ If a boundary condition is not specified it will default to 'slip wall'. In polyMesh/boundary
        "defaultFaces" is set to 'wall'.
        """
        print ('Setting default faces to use a slip boundary condition.')
        bc_names = listBoundaryNames(self._casePath)
        # NOTE: Code depreciated (JH) 07/02/2017
        # specified_bc_names = set([bc['name'] for bc in self._boundarySettings])
        # unspecified_bc_names = set(bc_names) - specified_bc_names
        # for bc in unspecified_bc_names:
        self._writeDefaultVelocityBoundary()
        self._writeDefaultPressureBoundary()
        if 'pointDisplacement' in self._solverCreatedVariables:
            self._initPressure_rghAsWall()
        # Thermal boundary init will be called in derived class
        for bc in bc_names:
            _default_wall_dict = {'name': bc, 'type': 'wall', 'subtype': 'slip'}
            # NOTE: Update code when added turbulence back to the code (JH)
            # self.setupWallTurbulence(_default_wall_dict, self._turbulenceProperties)

    def _writeDefaultVelocityBoundary(self):
        """ Default velocity boundary to slip wall. """
        f = ParsedParameterFile(self._casePath + "/0/U")
        for bc_name in listBoundaryNames(self._casePath):
            f["boundaryField"][bc_name] = {}
            f["boundaryField"][bc_name]["type"] = "slip"
        f.writeFile()

    def _writeDefaultPressureBoundary(self):
        """ Default pressure boundary to slip wall. """
        f = ParsedParameterFile(self._casePath + "/0/p")
        if 'p_rgh' in self._solverCreatedVariables:
            self._initPressure_rghAsWall()
            for bc_name in listBoundaryNames(self._casePath):
                f["boundaryField"][bc_name]["type"] = "zeroGradient"
        else:
            for bc_name in listBoundaryNames(self._casePath):
                f["boundaryField"][bc_name] = {"type": "zeroGradient"}
        f.writeFile()

    def _initPressure_rghAsWall(self):
        #
        p_rgh = ParsedParameterFile(self._casePath + "/0/p_rgh")
        for bc_name in listBoundaryNames(self._casePath):
            p_rgh["boundaryField"][bc_name] = {"type": "fixedFluxPressure", 'rho': 'rhok', 'value': "uniform 0"}
        p_rgh.writeFile()

    # NOTE: Code depreciated (JH) 06/02/2017
    # def _initPointDisplacementAsWall(self):
    #     #
    #     pd = ParsedParameterFile(self._casePath + "/0/pointDisplacement")
    #     for bc_name in listBoundaryNames(self._casePath):
    #         pd["boundaryField"][bc_name] = {"type": "fixedValue", 'value': "uniform (0 0 0)"}
    #     pd.writeFile()

    #####################################################################

    @property
    def boundaryConditions(self):
        return self._boundarySettings

    @boundaryConditions.setter
    def boundaryConditions(self, boundarySettings=None):
        if boundarySettings and isinstance(boundarySettings, list) and len(boundarySettings)>=1:
            self._boundarySettings = boundarySettings

    def setupBoundaryConditions(self, settings=None):
        if settings and isinstance(settings, list) and len(settings)>=1:
            self.boundaryConditions = settings

        self.writeDefaultBoundaryConditions()
        if not len(self._boundarySettings):
            print("Error: No boundary condition is defined, please check!")
        for bcDict in self._boundarySettings:
            if bcDict['type'] == 'inlet':
                if bcDict['subtype'] == 'totalPressure':
                    self.setupPressureInletBoundary(bcDict)
                else:  # massflow or uniformVelocity
                    self.setupVelocityInletBoundary(bcDict)
            elif bcDict['type'] == 'outlet' or bcDict['subtype'] == 'totalPressureOpening':
                self.setupOutletBoundary(bcDict)
            elif bcDict['subtype'] == 'freestream':
                self.setupFreestreamBoundary(bcDict)
            elif bcDict['type'] == 'wall':
                self.setupWallBoundary(bcDict)
            elif bcDict['type'] == 'constraint':
                self.setupConstraintBoundary(bcDict)
            elif bcDict['type'] == 'baffle':
                self.setupBaffleBoundary(bcDict)
            else:
                print("Warning: boundary type: {} is not supported yet and ignored!".format(bcDict['type']))
        # extra or special varialbe setup
        if 'p_rgh' in self._solverCreatedVariables:
            self._setupPressure_rgh()
        # pointDisplacement is implemented into setupWallBoundary, setupInletBoundary, etc

    def bafflesPresent(self):
        for bcDict in self._boundarySettings:
            if bcDict['type'] == 'baffle':
                return True
        return False

    def setupWallBoundary(self, bc_dict):
        """
        special wall boundary in OpenFOAM: fixed/noslip, slip, partialSlip, moving, rough
        wall turbulence setup has been done in `initTurbulenceBoundaryAsWall()`
        see: http://openfoam.com/documentation/cpp-guide/html/a11608.html
        """
        bc_name = bc_dict['name']
        wall_type = bc_dict['subtype']
        if 'velocity' in bc_dict:
            value = bc_dict['velocity']

        f = ParsedParameterFile(self._casePath + "/0/U")
        f["boundaryField"][bc_name] = {}
        if wall_type == 'fixed' or wall_type == 'noSlip':  # noSlip equal to fixed wall
            # A viscous wall (zero relative velocity between fluid/solid)
            # movingWallVelocity reduces to fixedValue if the mesh is not moving
            f["boundaryField"][bc_name]["type"] = "movingWallVelocity"
            f["boundaryField"][bc_name]["value"] = "uniform (0 0 0)"  # initial value
            # NOTE: Code depreciated (JH) 08/02/2017
            # if self._solverSettings['dynamicMeshing'] and "pointDisplacement" in self._solverCreatedVariables():
            #     df = ParsedParameterFile(self._casePath + "/0/pointDisplacement")
            #     df["boundaryField"][bc_name] = {'type': "calculated", 'value': 'uniform (0 0 0)'}
            #     df.writeFile()
        elif wall_type == 'rough':  # for turbulence flow only
            f["boundaryField"][bc_name]["type"] = "roughWall"
            f["boundaryField"][bc_name]["U"] = formatValue(value)
            print("Info: wall function for k, epsilon, omege nu may need set for roughwall")
        elif wall_type == 'slip':  # 100% slipping between solid and fluid
            f["boundaryField"][bc_name]["type"] = "slip"
            # TODO: check for dynamic meshing and warn. OF does not have a movingWallSlip
        elif wall_type == 'partialSlip':  # for multiphase flow
            f["boundaryField"][bc_name]["type"] = "partialSlip"
            f["boundaryField"][bc_name]["valueFraction"] = bc_dict['slipRatio']
            f["boundaryField"][bc_name]["value"] = "uniform (0 0 0)"
        elif wall_type == "translating":  # Specified velocity, only component tangential to wall is used
            f["boundaryField"][bc_name]["type"] = "translatingWallVelocity"
            f["boundaryField"][bc_name]["U"] = formatValue(value)
        else:
            print("wall boundary: {} is not supported yet".format(wall_type))
        f.writeFile()

        pf = ParsedParameterFile(self._casePath + "/0/p")
        pf["boundaryField"][bc_name] = {'type': "zeroGradient"}
        pf.writeFile()

        # NOTE: Update code when added turbulence back to the code (JH)
        # if 'turbulenceSettings' in bc_dict:
        #     turbulenceSettings = bc_dict['turbulenceSettings']
        # else:
        #     turbulenceSettings = self._turbulenceProperties
        # self.setupWallTurbulence(bc_dict, turbulenceSettings)

    # NOTE: Check implementation and remove 'cyclic' and 'wedge' (see trello note)
    def setupConstraintBoundary(self, bc_dict):
        # Geometrical constraint types
        case = self._casePath
        constraint_type = bc_dict['subtype']
        boundary_name = bc_dict['name']
        var_list = self._solverCreatedVariables
        for var in var_list:
            f = ParsedParameterFile(case + "/0/" + var)
            if constraint_type == "empty":
                f["boundaryField"]["frontAndBack"] = {}
                f["boundaryField"]["frontAndBack"]["type"] = "empty"
                # axis-sym 2D case, axis line is also empty type
            elif constraint_type == "symmetryPlane" or constraint_type == "symmetry":
                f["boundaryField"][boundary_name] = {}
                f["boundaryField"][boundary_name]["type"] = constraint_type
            elif constraint_type == "cyclic": # also named as `periodic` in ansys Fluent
                f["boundaryField"][boundary_name] = {}
                f["boundaryField"][boundary_name]["type"] = "cyclic"
                # Todo: check pairing of wedge and cyclic boundary
            elif constraint_type == "wedge":
                f["boundaryField"][boundary_name] = {}
                f["boundaryField"][boundary_name]["type"] = "wedge"  # axis-sym
            else:
                raise Exception('Boundary or patch type {} is not supported'.format(constraint_type))
            f.writeFile()

    def pairCyclicBoundary(self, type, names):
        """
        http://www.cfdsupport.com/OpenFOAM-Training-by-CFD-Support/node108.html
        inGroups 1(cyclicAMI); neighbourPatch <ref to the paired patch name>
        #boundary file needs to be modified, 
        'transform' = roational, rotationAxis. rotatingCentre
        'transform' = translational; separationVector = 
        """
        pass

    def _setupPressure_rgh(self):
        # Pseudo hydrostatic pressure [Pa] : p - rho * g * height
        # only for buoyant flow in heat transfer in compressible and incompressible flow
        # /opt/openfoam4/tutorials/heatTransfer/chtMultiRegionSimpleFoam/heatExchanger/0.orig/porous
        # /opt/openfoam4/tutorials/heatTransfer/buoyantSimpleFoam/circuitBoardCooling/0.orig
        # prghTotalPressure,
        # buoyantPressure for heat exchanger wall, value uniform 0;
        # source doc: http://www.openfoam.com/documentation/cpp-guide/html/a02111.html#details

        f = ParsedParameterFile(self._casePath + "/0/p_rgh")
        for bc_dict in self._boundarySettings:
            bc = bc_dict['name']
            subtype = bc_dict['subtype']
            if bc_dict['type'] in set(['inlet', 'outlet']):
                if bc_dict['subtype'] in set(["staticPressure", "pressure"]):
                    f["boundaryField"][bc] = {'type': 'prghPressure', 'p': formatValue(bc_dict['pressure'])}
                if bc_dict['subtype'] == "totalPressure":
                    f["boundaryField"][bc] = {'type': 'prghTotalPressure', 'p0': formatValue(bc_dict['pressure'])}
                else:
                    f["boundaryField"][bc] = {'type': 'fixedFluxPressure', 'gradient':'uniform 0', 'value': "$internalField"}
            elif bc_dict['subtype'] == 'freestream':
                f["boundaryField"][bc] = {'type': 'fixedValue', 'value': "$internalField"} #todo: check freestreamPressure
            elif bc_dict['type'] == 'constraint':
                f["boundaryField"][bc] = {'type': subtype}
            elif bc_dict['type'] == 'wall':
                f["boundaryField"][bc] = {'type': 'fixedFluxPressure', 'value': 'uniform 0'}
            else:
                print("Warning: boundary type: {} is not supported in p_rgh thus ignored!".format(bc_dict['type']))
        f.writeFile()

    def setupPressureInletBoundary(self, bc_dict):
        bc_name = bc_dict['name']
        inlet_type = bc_dict['subtype']
        value = bc_dict['pressure']

        pf = ParsedParameterFile(self._casePath + "/0/p")
        pf["boundaryField"][bc_name] = {}
        Uf = ParsedParameterFile(self._casePath + "/0/U")
        Uf["boundaryField"][bc_name] = {}

        if 'p_rgh' in self._solverCreatedVariables:
            pf["boundaryField"][bc_name] = {'type': 'calculated', 'value': "$internalField"}
        else:
            if inlet_type == "totalPressure":
                pf["boundaryField"][bc_name]["type"] = 'totalPressure'
                pf["boundaryField"][bc_name]["p0"] = 'uniform {}'.format(value)
                pf["boundaryField"][bc_name]["value"] = "$internalField"  # initial value
            else:  #
                pf["boundaryField"][bc_name]["type"] = 'fixedValue'
                pf["boundaryField"][bc_name]["value"] = "uniform {}".format(value)
        pf.writeFile()

        # Velocity boundary defaults to wall, so it needs to change
        Uf["boundaryField"][bc_name]["type"] = "pressureInletOutletVelocity"
        Uf["boundaryField"][bc_name]["value"] = "uniform (0 0 0)"  # initial value
        Uf.writeFile()

        # NOTE: Update code when added turbulence back to the code (JH)
        # if 'turbulenceSettings' in bc_dict:
        #     turbulenceSettings = bc_dict['turbulenceSettings']
        # else:
        #     turbulenceSettings = self._turbulenceProperties
        # self.setupInletTurbulence(bc_dict, turbulenceSettings)

    def setupVelocityInletBoundary(self, bc_dict):
        """ direction: by default, normal to inlet boundary
        """
        bc_name = bc_dict['name']
        inlet_type = bc_dict['subtype']
        value = bc_dict['velocity']

        # velocity intial value is default to wall: uniform (0,0,0)
        Uf = ParsedParameterFile(self._casePath + "/0/U")
        Uf["boundaryField"][bc_name] = {}
        if inlet_type == "massFlowRate":
            Uf["boundaryField"][bc_name]["type"] = "flowRateInletVelocity"
            Uf["boundaryField"][bc_name]["massFlowRate"] = bc_dict['massFlowRate']  # kg/s
            Uf["boundaryField"][bc_name]["rho"] = "rho"
            # Set rhoInlet in case rho field is not found
            for k in ['rho', 'density']:
                if k in self._fluidProperties:
                    Uf["boundaryField"][bc_name]["rhoInlet"] = self._fluidProperties[k]
            Uf["boundaryField"][bc_name]["value"] = "$internalField"
        elif inlet_type == "volumetricFlowRate":
            Uf["boundaryField"][bc_name]["type"] = "flowRateInletVelocity"
            Uf["boundaryField"][bc_name]["volumetricFlowRate"] = bc_dict['volFlowRate']  # m3/s
            Uf["boundaryField"][bc_name]["value"] = "$internalField"
        elif inlet_type == "uniformVelocity":
            assert len(value) == 3  # velocity must be a tuple or list with 3 components
            '''
                This fixes all three components of velocity on inflow and only the normal component on outflow,
                in order to be well-posed if there are some faces on the patch which are actually outflows.
            '''
            Uf["boundaryField"][bc_name]["type"] = "fixedNormalInletOutletVelocity"
            Uf["boundaryField"][bc_name]["fixTangentialInflow"] = "yes"
            Uf["boundaryField"][bc_name]["normalVelocity"] = {}
            Uf["boundaryField"][bc_name]["normalVelocity"]["type"] = "fixedValue"
            Uf["boundaryField"][bc_name]["normalVelocity"]["value"] = formatValue(value)
            Uf["boundaryField"][bc_name]["value"] = formatValue(value)
        else:
            print(inlet_type + " is not supported as inlet boundary type")
        Uf.writeFile()

        pf = ParsedParameterFile(self._casePath + "/0/p")
        if 'p_rgh' in self._solverCreatedVariables:
            pf["boundaryField"][bc_name] = {'type': 'calculated', 'value': "$internalField"}
        else:
            pf["boundaryField"][bc_name] = {}
            pf["boundaryField"][bc_name]["type"] = "zeroGradient"
            # pf["boundaryField"][bc_name]["value"] = "uniform 0" # zG does not require value
        pf.writeFile()

        # NOTE: Update code when added turbulence back to the code (JH)
        # if 'turbulenceSettings' in bc_dict:
        #     turbulenceSettings = bc_dict['turbulenceSettings']
        # else:
        #     turbulenceSettings = self._turbulenceProperties
        # self.setupInletTurbulence(bc_dict, turbulenceSettings)

    def setupOutletBoundary(self, bc_dict):
        """supported_outlet_types: outFlow, pressureOutlet
        pressureOutlet, for exit to background static pressure
        outFlow: corresponding to velocityInlet/FlowRateInlet
        self.supported_outlet_types = set([])
        http://cfd.direct/openfoam/user-guide/boundaries/
        inletOutlet: Switches U and p between fixedValue and zeroGradient depending on direction of U
        pressureInletOutletVelocity: Combination of pressureInletVelocity and inletOutlet
        """
        bc_name = bc_dict['name']
        outlet_type = bc_dict['subtype']
        value = bc_dict['pressure']

        pf = ParsedParameterFile(self._casePath + "/0/p")
        pf["boundaryField"][bc_name] = {}
        if outlet_type == "totalPressureOpening":  # For outflow, totalPressure BC actually imposes static pressure
            pf["boundaryField"][bc_name]["type"] = 'totalPressure'
            pf["boundaryField"][bc_name]["p0"] = 'uniform {}'.format(bc_dict['pressure'])
            pf["boundaryField"][bc_name]["value"] = "$internalField"  # initial value
        elif outlet_type == "staticPressure":
            pf["boundaryField"][bc_name]["type"] = 'fixedValue'
            pf["boundaryField"][bc_name]["value"] = 'uniform {}'.format(value)
        elif outlet_type == "uniformVelocity":
            pf["boundaryField"][bc_name]["type"] = "zeroGradient"
        elif outlet_type == "outFlow":
            pf["boundaryField"][bc_name]["type"] = "zeroGradient"
            pf["boundaryField"][bc_name]["value"] = "$internalField"
        else:
            pf["boundaryField"][bc_name]["type"] = "zeroGradient"
            print("pressure boundary default to zeroGradient for outlet type '{}' ".format(outlet_type))
        pf.writeFile()

        value = bc_dict['velocity']
        # velocity intial value is default to wall, uniform 0, so it needs to change
        Uf = ParsedParameterFile(self._casePath + "/0/U")
        Uf["boundaryField"][bc_name] = {}
        if outlet_type == "totalPressure" or outlet_type == 'staticPressure':
            Uf["boundaryField"][bc_name]["type"] = "pressureInletOutletVelocity"
            Uf["boundaryField"][bc_name]["value"] = "$internalField"  # set as initial value only
        elif outlet_type == "uniformVelocity":
            '''
                This fixes only the normal component on outflow and all three components of velocity on inflow,
                in order to be well-posed on outflow and also in case there are any faces with inflowing velocity.
            '''
            Uf["boundaryField"][bc_name]["type"] = "fixedNormalInletOutletVelocity"
            Uf["boundaryField"][bc_name]["fixTangentialInflow"] = "true"
            Uf["boundaryField"][bc_name]["normalVelocity"]["type"] = "fixedValue"
            Uf["boundaryField"][bc_name]["normalVelocity"]["value"] = formatValue(value)
            Uf["boundaryField"][bc_name]["value"] = formatValue(value)
        elif outlet_type == "outFlow":
            Uf["boundaryField"][bc_name]["type"] = "inletOutlet"
            Uf["boundaryField"][bc_name]["inletValue"] = "uniform (0 0 0)"
            # TODO: We need to write an out-flowing value here so that adjustPhi can have an adjustable flux to work
            # TODO: with at iteration 1
            Uf["boundaryField"][bc_name]["value"] = "$internalField"
        else:
            print("velocity boundary set to inletOutlet for outlet type '{}' ".format(outlet_type))
            Uf["boundaryField"][bc_name]["type"] = "zeroGradient"
        Uf.writeFile()

        # NOTE: Update code when added turbulence back to the code (JH)
        # if 'turbulenceSettings' in bc_dict:
        #     turbulenceSettings = bc_dict['turbulenceSettings']
        # else:
        #     turbulenceSettings = self._turbulenceProperties
        # self.setupOutletTurbulence(bc_dict, turbulenceSettings)

    def setupFreestreamBoundary(self, bc_dict):
        """ freestream is the known velocity in far field of open space
        see: tutorials/incompressible/simpleFoam/airFoil2D/0.org/
        """
        print('internalField must be set for each var in 0/ folder')
        bc_name = bc_dict['name']
        value = bc_dict['velocity']
        #
        f = ParsedParameterFile(self._casePath + "/0/p")
        f["boundaryField"][bc_name] = {}
        f["boundaryField"][bc_name]["type"] = "freestreamPressure"
        f.writeFile()
        #
        f = ParsedParameterFile(self._casePath + "/0/U")
        f["boundaryField"][bc_name] = {}
        f["boundaryField"][bc_name]["type"] = "freestream"
        f["boundaryField"][bc_name]["value"] = formatValue(value)
        f.writeFile()

        # NOTE: Update code when added turbulence back to the code (JH)
        # if 'turbulenceSettings' in bc_dict:
        #     turbulenceSettings = bc_dict['turbulenceSettings']
        # else:
        #     turbulenceSettings = self._turbulenceProperties
        # self.setupFreestreamTurbulence(bc_dict, turbulenceSettings)

    def setupBaffleBoundary(self, bcDict):
        case = self._casePath
        sub_type = bcDict['subtype']
        var_list = self._solverCreatedVariables
        if sub_type == "porousBaffle":
            for var in var_list:
                # It is not strictly necessary to do master and slave, as one can use the baffle group to refer
                # to both. However, we create both to keep paraview happy.
                for masterSlave in ["master", "slave"]:
                    bcName = bcDict['name'] + "_" + masterSlave
                    f = ParsedParameterFile(case + "/0/" + var)
                    f["boundaryField"][bcName] = {}
                    if var == "p" or var == "p_rgh":
                        f["boundaryField"][bcName]["type"] = "porousBafflePressure"
                        f["boundaryField"][bcName]["patchType"] = "cyclic"
                        f["boundaryField"][bcName]["length"] = "1.0"
                        f["boundaryField"][bcName]["I"] = str(bcDict['pressureDropCoeff'])
                        f["boundaryField"][bcName]["D"] = "0"
                        f["boundaryField"][bcName]["value"] = "$internalField"
                    else:
                        f["boundaryField"][bcName]["type"] = "cyclic"
                    f.writeFile()
        else:
            raise Exception('Baffle type {} is not supported'.format(sub_type))

    def setupCreateBafflesDict(self):
        fname = os.path.join(self._casePath, "system", "createBafflesDict")
        fid = open(fname, 'w')

        baffles = ""
        for bc in self._boundarySettings:
            if bc['type'] == 'baffle':
                baffles += readTemplate(os.path.join(self._templatePath, "helperFiles", "createBafflesDictBaffle"),
                                        {"NAME": bc['name']})
        fid.write(readTemplate(os.path.join(self._templatePath, "helperFiles", "createBafflesDict"),
                               {"HEADER": readTemplate(os.path.join(self._templatePath, "helperFiles", "header"),
                                                       {"LOCATION": "system",
                                                        "FILENAME": "createBafflesDict"}),
                                "BAFFLES": baffles}))
        fid.close()

    @property
    def porousZoneSettings(self):
        return self._porousZoneSettings

    @porousZoneSettings.setter
    def porousZoneSettings(self, porousZoneSettings=[]):
        if isinstance(porousZoneSettings, list):
            self._porousZoneSettings = porousZoneSettings
        else:
            raise Exception("Porous settings must be a list.")

    def setupTopoSetDict(self):
        porousObject = self._porousZoneSettings
        fname = os.path.join(self._casePath, "system", "topoSetDict")
        fid = open(fname, 'w')

        actions = ""
        for po in porousObject:
            for partName in po['PartNameList']:
                actions += readTemplate(os.path.join(self._templatePath, "helperFiles", "topoSetDictStlToCellZone"),
                                        {"CELLSETNAME": partName+"SelectedCells",
                                         "STLFILE": os.path.join("constant",
                                                                 "triSurface",
                                                                 partName+u"Scaled.stl"),
                                         "CELLZONENAME": partName})

        fid.write(readTemplate(os.path.join(self._templatePath, "helperFiles", "topoSetDict"),
                               {"HEADER": readTemplate(os.path.join(self._templatePath, "helperFiles", "header"),
                                                       {"LOCATION": "system",
                                                        "FILENAME": "topoSetDict"}),
                                "ACTIONS": actions}))
        fid.close()

    def setupCreatePatchDict(self, case_folder, bc_group, mobj):
        print ('Populating createPatchDict to update BC names')
        fname = os.path.join(case_folder, "system", "createPatchDict")
        fid = open(fname, 'w')
        patch = ""

        bc_allocated = []
        for bc_id, bc_obj in enumerate(bc_group):
            bc_list = []
            meshFaceList = mobj.Part.Shape.Faces
            for (i, mf) in enumerate(meshFaceList):
                bcFacesList = bc_obj.Shape.Faces
                for bf in bcFacesList:
                    import FemMeshTools
                    isSameGeo = FemMeshTools.is_same_geometry(bf, mf)
                    if isSameGeo:
                        bc_list.append(mobj.ShapeFaceNames[i])
                        if mobj.ShapeFaceNames[i] in bc_allocated:
                            print ('Error: {} has been assigned twice'.format(mobj.ShapeFaceNames[i]))
                        else:
                            bc_allocated.append(mobj.ShapeFaceNames[i])

            bc_list_str = ""
            for bc in bc_list:
                bc_list_str += " " + bc

            bcDict = bc_obj.BoundarySettings
            bcType = bcDict["BoundaryType"]
            bcSubType = bcDict["BoundarySubtype"]
            patchType = getPatchType(bcType, bcSubType)

            patch += readTemplate(
                os.path.join(self._templatePath, "helperFiles", "createPatchDictPatch"),
                {"LABEL": bc_obj.Label,
                 "TYPE": patchType,
                 "PATCHLIST": bc_list_str})

            if not (len(bc_list) == len(meshFaceList)):
                print('Error: Miss-match between boundary faces and mesh faces')

        # Add default faces
        flagName = False
        bc_list_str = ""
        for name in mobj.ShapeFaceNames:
            if not name in bc_allocated:
                bc_list_str += " " + name
                flagName = True
        if (flagName):
            patch += readTemplate(
                os.path.join(self._templatePath, "helperFiles", "createPatchDictPatch"),
                {"LABEL": 'defaultFaces',
                 "TYPE": 'patch',
                 "PATCHLIST": bc_list_str})

        fid.write(readTemplate(os.path.join(self._templatePath, "helperFiles", "createPatchDict"),
                               {"HEADER": readTemplate(os.path.join(self._templatePath, "helperFiles", "header"),
                                                       {"LOCATION": "system",
                                                        "FILENAME": "createPatchDict"}),
                                "PATCH": patch}))
        fid.close()


    def setupFVOptions(self):
        porousObject = self._porousZoneSettings
        fname = os.path.join(self._casePath, "constant", "fvOptions")
        fid = open(fname, 'w')

        sources = ""
        for po in porousObject:
            for partName in po['PartNameList']:
                sources += readTemplate(os.path.join(self._templatePath, "helperFiles", "fvOptionsPorousZone"),
                                        {"SOURCENAME": partName,
                                         "DX": str(po['D'][0]),
                                         "DY": str(po['D'][1]),
                                         "DZ": str(po['D'][2]),
                                         "FX": str(po['F'][0]),
                                         "FY": str(po['F'][1]),
                                         "FZ": str(po['F'][2]),
                                         "E1X": str(po['e1'][0]),
                                         "E1Y": str(po['e1'][1]),
                                         "E1Z": str(po['e1'][2]),
                                         "E3X": str(po['e3'][0]),
                                         "E3Y": str(po['e3'][1]),
                                         "E3Z": str(po['e3'][2]),
                                         "CELLZONENAME": partName})

        fid.write(readTemplate(os.path.join(self._templatePath, "helperFiles", "fvOptions"),
                               {"HEADER": readTemplate(
                                                       os.path.join(self._templatePath, "helperFiles", "header"),
                                                       {"LOCATION": "constant",
                                                        "FILENAME": "fvOptions"}),
                                "SOURCES": sources}))
        fid.close()

    # NOTE: Update code when adding turbulence (JH)
    # Turbulence settings and boundary conditions


    # @property
    # def turbulenceProperties(self):
    #     return self._turbulenceProperties
    #
    # @turbulenceProperties.setter
    # def turbulenceProperties(self, tSettings=None):
    #     """ see list of turbulence model: http://www.openfoam.org/features/turbulence.php
    #     OpenFoam V3.0 has unified turbuence setup dic, incompatible with 2.x
    #     currently only some common RAS models are settable by this script
    #     """
    #     if tSettings:
    #         self._turbulenceProperties = tSettings
    #         if _debug:
    #             print(self._turbulenceProperties)

    def setupTurbulenceProperties(self, turbulenceProperties=None):
        """ ... """
        case = self._casePath
        turbulence_model_name = self._physicsModel["Turbulence"]
        fname = case + "/constant/turbulenceProperties"

        if not os.path.exists(fname):
            lines = ["simulationType     laminar;"]
            createRawFoamFile(case, "constant", "turbulenceProperties", lines)
        f = ParsedParameterFile(case + "/constant/turbulenceProperties")
        if turbulence_model_name == 'Laminar':
            f['simulationType'] = "laminar"
        # NOTE: Update code when added turb back in (JH)
        #     if 'RAS' in f:
        #         del f['RAS']  # clear this content
        # elif turbulance_model_name in RAS_turbulence_models:
        #     f['simulationType'] = "RAS"
        #     # if getFoamVariant() == "OpenFOAM" and getFoamVersion()[0] >= 3:
        #     if getFoamVersion()[0] >= 3:
        #         f['RAS'] = {'RASModel': turbulance_model_name, 'turbulence': "on", 'printCoeffs': "on"}
        #         if turbulance_model_name in kEpsilon_models and 'kEpsilonCoeffs' in self._turbulenceProperties:
        #             f['kEpsilonCoeffs'] = self._turbulenceProperties['kEpsilonCoeffs']
        #         # need check again, other model may need diff parameter
        #     else:
        #         fRAS = ParsedParameterFile(case + "/constant/RASProperties")
        #         fRAS['RASModel'] = turbulance_model_name
        #         fRAS['turbulence'] = "on"
        #         fRAS['printCoeffs'] = "on"
        #         # modify coeff is it is diff from default (coded into source code)
        #         if turbulance_model_name == "kEpsilon" and 'kEpsilonCoeffs' in self._turbulenceProperties:
        #             fRAS['kEpsilonCoeffs'] = self._turbulenceProperties['kEpsilonCoeffs']
        #         fRAS.writeFile()
        # NOTE: Code depreciated (JH) 07/02/2017
        # elif turbulance_model_name in LES_turbulence_models:
        #     # if getFoamVariant() == "OpenFOAM" and getFoamVersion()[0] >= 3:
        #     if getFoamVersion()[0] >= 3:
        #         # all LES model setup is done in file 'turbulenceProperties'
        #         if not os.path.exists(fname):
        #             createRawFoamFile(case, "constant", "turbulenceProperties",
        #                                 getLeSTurbulencePropertiesTemplate(turbulance_model_name))
        #     else:
        #         print("Assumeing LESTurbulenceProperties is copied from template file for OpenFOAM 2.x or foam-extend")
        else:
            print("Turbulence model {} is not recognised or implemented".format(turbulence_model_name))
        f.writeFile()

    #
    # def listTurbulenceVarables(self):
    #     """specific turbulenceModel name:  kEpsilon, kOmegaSST, SpalartAllmaras
    #     SpalartAllmaras: incompressible/simpleFoam/airFoil2D
    #     'mut', used in compressible fluid
    #     """
    #     solverSettings = self._solverSettings
    #     return getTurbulenceVariables(solverSettings)
    #
    # def setupWallTurbulence(self, bc_dict, turbulenceSettings):
    #     """ set all boundary condition to default: wall, also set wallFunction for each var
    #     for y+<1 (viscous sublayer) turbulent field = 0, if y+>30, wall function should be used
    #     - compressible flow has suffex for nut: see tutorial of `rhoSimpleFoam`
    #     - diff turbulence modle has diff wall function: nutSpalartAllmarasWallFunction
    #     - rough wall has speicial wall function: not supported yet
    #     - wall function can be related with velocity U, not supported yet
    #     - low Reynolds model has suffex `lowRe`: supported
    #     #includeEtc "caseDicts/setConstraintTypes"
    #     compressible cases have different wall functions with a suffix for OpenFOAM 2.x
    #     """
    #     case = self._casePath
    #     turbulence_var_list = self.listTurbulenceVarables()
    #     if self._physicsModel['Flow'] == 'Compressible':
    #         suffix = 'compressible::'  # only `alphat` is needed for OpenFOAM 3.0+
    #     else:
    #         suffix = ''
    #     #print(turbulence_model)
    #     if self._solverSettings['turbulenceModel'] in lowRe_models:
    #         print('Warning: low Reynolds wall function is not supported yet')
    #         lowRe = "LowRe"
    #         kWallFunction = 'kLowReWallFunction'
    #     else:
    #         lowRe = ""
    #         kWallFunction = 'kqRWallFunction'
    #
    #     for var in turbulence_var_list:
    #         f = ParsedParameterFile(case + "/0/" + var)
    #         # kOmega has nonzero internalField for k, omega and epsilon, set default in CreateInitVarables()
    #         bc_name = bc_dict['name']
    #         # if boundaryType == 'wall' and 'type == 'rough':
    #         #   print('rough wall boundary is not support yet')
    #         f["boundaryField"][bc_name] = {}
    #         if var == 'k' or var.find("k.") == 0: #begin with
    #             f["boundaryField"][bc_name]["value"]="$internalField"
    #             f["boundaryField"][bc_name]["type"]=kWallFunction  # depend on turbulence_model!!!
    #
    #         elif var == 'epsilon' or var.find("epsilon") == 0:
    #             f["boundaryField"][bc_name]["type"]= var + lowRe + "WallFunction"
    #             f["boundaryField"][bc_name]["value"]="$internalField" #
    #
    #         elif var == 'omega' or var.find("omega") == 0:
    #             f["boundaryField"][bc_name]["type"]= var + lowRe + "WallFunction"
    #             f["boundaryField"][bc_name]["value"]="$internalField"
    #         # alphaT may be init/setup again in derived class thermal builder
    #         elif var == "alphat" or var.find("alphat") == 0:
    #             f["boundaryField"][bc_name]["type"] = "calculated"
    #             f["boundaryField"][bc_name]["value"] = "$internalField"
    #
    #         elif  var == 'nut' or var.find("nut.") == 0:  # nut nutk
    #             if  turbulenceSettings['name'] in spalartAllmaras_models:
    #                 f["boundaryField"][bc_name]["value"]="uniform 0"
    #                 f["boundaryField"][bc_name]["type"]="nutSpalartAllmarasWallFunction" # or 'nutUSpaldingWallFunction'
    #                 print('Info: nutSpalartAllmarasWallFunction/nutUSpaldingWallFunction can be used for spalartAllmaras turbulence model')
    #             else:
    #                 f["boundaryField"][bc_name]["value"]="$internalField"
    #                 f["boundaryField"][bc_name]["type"]="nutkWallFunction"  # calculated for other type
    #
    #         elif var == "nuTilda" or var.find("nuTilda.") == 0:   # for LES model and SpalartAllmaras RAS models
    #             f["boundaryField"][bc_name]["type"]="zeroGradient"  # 'value' not needed, same for LES
    #         else:
    #             print("Warning: turbulent var {} is not recognised thus ignored".format(var))
    #         f.writeFile()
    #
    # def setupInletTurbulence(self, bc_dict, turbulenceSettings):
    #     """ modeled from case tutorials/incompressible/simpleFoam/pipeCyclic/0.org
    #     available turbulentce spec:
    #     - Set k and epislon explicitly.
    #     - Set turbulence intensity and turbulence length scale.
    #     - Set turbulence intensity and turbulent viscosity ratio
    #     - Set turbulence intensity and hydraulic diameter
    #     """
    #     case = self._casePath
    #     bc_name = bc_dict['name']
    #     turbulence_var_list = self.listTurbulenceVarables()
    #
    #     if "turbulentIntensity" in turbulenceSettings:
    #         turbulentIntensity = turbulenceSettings["intensityValue"]
    #     else:
    #         turbulentIntensity = 0.05  # 5% default, a reasonable guess
    #     if "hydrauicDiameter" in turbulenceSettings:
    #         turbulentMixingLength = 0.5 * turbulenceSettings["lengthValue"]
    #     else:
    #         turbulentMixingLength = 0.1  # in metre, half inlet diam/width
    #     #print(turbulence_var_list)
    #     for var in turbulence_var_list:
    #         f = ParsedParameterFile(case + "/0/" + var)
    #         f["boundaryField"][bc_name] = {}
    #         if var == 'k' or var.find("k.") == 0: #begin with
    #             f["boundaryField"][bc_name]["type"] = "turbulentIntensityKineticEnergyInlet"
    #             f["boundaryField"][bc_name]["intensity"] = turbulentIntensity
    #             f["boundaryField"][bc_name]["value"] = "$internalField"
    #
    #         elif var == 'epsilon' or var.find("epsilon") == 0:
    #             f["boundaryField"][bc_name]["type"] = "turbulentMixingLengthDissipationRateInlet"
    #             f["boundaryField"][bc_name]["mixingLength"] = turbulentMixingLength
    #             f["boundaryField"][bc_name]["value"] = "$internalField"
    #
    #         elif var == 'omega' or var.find("omega") == 0:
    #             # /opt/openfoam4/etc/templates/axisymmetricJet
    #             f["boundaryField"][bc_name]["type"] = "turbulentMixingLengthFrequencyInlet"
    #             f["boundaryField"][bc_name]["mixingLength"] = turbulentMixingLength
    #             f["boundaryField"][bc_name]["value"] = "$internalField"
    #
    #         elif var == "alphat" or var.find("alphat") == 0:
    #             f["boundaryField"][bc_name]["type"] = {"type": "calculated",  "value": "$internalField"}
    #
    #         elif  var == 'nut' or var.find("nut.") == 0:
    #             f["boundaryField"][bc_name] = {"type": "calculated",  "value": "$internalField"}
    #
    #         elif var == "nuTilda" or var.find("nuTilda.") == 0:
    #             f["boundaryField"][bc_name] = {"type": "zeroGradient"} #zeroGradient; for wall, inlet and outlet
    #         else:
    #             print("Warning: turbulent var {} is not recognised thus ignored".format(var))
    #         f.writeFile()
    #
    # def setupOutletTurbulence(self, bc_dict, turbulenceSettings):
    #     case = self._casePath
    #     bc_name = bc_dict['name']
    #     turbulence_var_list = self.listTurbulenceVarables()
    #     for var in turbulence_var_list:
    #         f = ParsedParameterFile(self._casePath + "/0/" + var)
    #         f["boundaryField"][bc_name] = {}
    #         if var == 'k' or var.find("k.") == 0: #begin with
    #             f["boundaryField"][bc_name]["type"] = "inletOutlet"
    #             f["boundaryField"][bc_name]["inletValue"] = "$internalField"
    #             f["boundaryField"][bc_name]["value"] = "$internalField"
    #
    #         elif var == 'epsilon' or var.find("epsilon") == 0:
    #             f["boundaryField"][bc_name]["type"] = "inletOutlet"
    #             f["boundaryField"][bc_name]["inletValue"] = "$internalField"
    #             f["boundaryField"][bc_name]["value"] = "$internalField"
    #
    #         elif var == 'omega' or var.find("omega") == 0:
    #             f["boundaryField"][bc_name]["type"] = "inletOutlet"
    #             f["boundaryField"][bc_name]["inletValue"] = "$internalField"
    #             f["boundaryField"][bc_name]["value"] = "$internalField"
    #
    #         elif var == "alphat" or var.find("alphat") == 0:
    #             f["boundaryField"][bc_name]["type"] = "calculated"
    #             f["boundaryField"][bc_name]["value"] = "$internalField"
    #
    #         elif  var == 'nut' or var.find("nut.") == 0:
    #             f["boundaryField"][bc_name]["type"] = "calculated"
    #             f["boundaryField"][bc_name]["value"] = "$internalField"
    #
    #         elif var == "nuTilda" or var.find("nuTilda.") == 0:
    #             f["boundaryField"][bc_name]["type"] = "zeroGradient"
    #             #zeroGradient; same for wall, inlet and outlet
    #         else:
    #             print("Warning: turbulent var {} is not recognised thus ignored".format(var))
    #         f.writeFile()
    #
    # def setupFreestreamTurbulence(self, bc_dict, turbulenceSettings):
    #     # see: tutorials/incompressible/simpleFoam/airFoil2D/0.org/  SA model
    #     # tutorial for other RAS model?  k, omege, epsilon, nut, alphat,  "calculated"?
    #     case = self._casePath
    #     bc_name = bc_dict['name']
    #     bType = bc_dict['type']
    #     subtype = bc_dict['subtype']
    #     turbulence_var_list = self.listTurbulenceVarables()
    #     if not "freestreamValue" in turbulenceSettings:
    #         turbulenceSettings["freestreamValue"] = '$internalField'
    #     for v in turbulence_var_list:
    #         f = ParsedParameterFile(self._casePath + "/0/" + v)
    #         f["boundaryField"][bc_name] = {}
    #         if v.split('.')[0] in set(['nut', 'nuTilda', 'alphat']):
    #             f["boundaryField"][bc_name]["type"] = "freestream"
    #             f["boundaryField"][bc_name]["freestreamValue"] = "uniform {}".format(turbulenceSettings["freestreamValue"])
    #         elif v.split('.')[0] in set(['k', 'epsilon', 'omega']):
    #             f["boundaryField"][bc_name]["type"] = "calculated"
    #             f["boundaryField"][bc_name]["value"] = "uniform {}".format(turbulenceSettings["freestreamValue"])
    #         else:
    #             print("Warning: turbulent var {} is not recognised thus ignored".format(var))
    #         f.writeFile()

    # NOTE: Code depreciated (JH) 07/02/2017
    # def setupInterfaceTurbulence(self, bc_dict, turbulenceSettings):
    #     """ ... """
    #     bc_name = bc_dict['name']
    #     subtype = bc_dict['subtype']
    #     for v in turbulence_var_list:
    #         f = ParsedParameterFile(self._casePath + "/0/" + v)
    #         f["boundaryField"][bc_name] = {}
    #         f["boundaryField"][bc_name]["type"] = subtype
    #         f.writeFile()