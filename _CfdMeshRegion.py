# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2016 - Bernd Hahnebach <bernd@bimstatik.org>            *
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

__title__ = "_CfdMeshRegion"
__author__ = "Bernd Hahnebach"
__url__ = "http://www.freecadweb.org"

## @package CfdMeshRegion
#  \ingroup CFD


class _CfdMeshRegion:
    """The CfdMeshRegion object"""
    def __init__(self, obj):
        obj.addProperty("App::PropertyFloat",
                        "RelativeLength",
                        "MeshRegionProperties",
                        "Set relative length of the elements for this region")
        obj.addProperty("App::PropertyLength",
                        "RefinementThickness",
                        "MeshRegionProperties",
                        "Set refinement region thickness")
        obj.RefinementThickness = 0.0
        obj.addProperty("App::PropertyInteger",
                        "NumberLayers",
                        "MeshRegionProperties",
                        "Set number of boundary layers")
        obj.NumberLayers = 0
        obj.addProperty("App::PropertyFloat",
                        "ExpansionRatio",
                        "MeshRegionProperties",
                        "Set expansion ratio within boundary layers")
        obj.ExpansionRatio = 0.0
        obj.addProperty("App::PropertyLength",
                        "FirstLayerHeight",
                        "MeshRegionProperties",
                        "Set the maximum first layer height")
        obj.FirstLayerHeight = 0.0

        obj.addProperty("App::PropertyLinkSubList", "References", "MeshRegionShapes", "List of mesh region shapes")
        obj.Proxy = self
        self.Type = "CfdMeshRegion"

    def execute(self, obj):
        return
