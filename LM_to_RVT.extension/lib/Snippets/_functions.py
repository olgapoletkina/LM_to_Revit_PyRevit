# -*- coding: utf-8 -*-

import sys
import clr
clr.AddReference('ProtoGeometry')
clr.AddReference('RevitServices')
from RevitServices.Persistence import DocumentManager
clr.AddReference('RevitNodes')
import Revit
clr.ImportExtensions(Revit.Elements)
clr.ImportExtensions(Revit.GeometryConversion)
clr.AddReference('RevitAPI')
from Autodesk.Revit import DB
from Autodesk.Revit.DB import FilteredElementCollector as FEC
from System.Collections.Generic import List
from Autodesk.Revit.UI import Selection as SEL

uiapp = __revit__
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = __revit__.Application

# working with units

def unit_converter(
        doc,
        value,
        to_internal=False,
        unit_type=DB.SpecTypeId.Length,
        number_of_digits=None):
    display_units = doc.GetUnits().GetFormatOptions(unit_type).GetUnitTypeId()
    method = DB.UnitUtils.ConvertToInternalUnits if to_internal \
        else DB.UnitUtils.ConvertFromInternalUnits
    if number_of_digits is None:
        return method(value, display_units)
    elif number_of_digits > 0:
        return round(method(value, display_units), number_of_digits)
    return int(round(method(value, display_units), number_of_digits))

# working with list structure

def flatten(element, flat_list=None):

    '''gets the list with complex structure, 
    returns flattened list of elements'''

    if flat_list is None:
        flat_list = []
    if hasattr(element, "__iter__"):
        for item in element:
            flatten(item, flat_list)
    else:
        flat_list.append(element)
    return flat_list

def to_list(element, list_type=None):
    if not hasattr(element, '__iter__') or isinstance(element, dict):
        element = [element]
    if list_type is not None:
        if isinstance(element, List[list_type]):
            return element
        if all(isinstance(item, list_type) for item in element):
            typed_list = List[list_type]()
            for item in element:
                typed_list.Add(item)
            return typed_list
    return element

def group_by_key(elements, key_type='Type'):
    elements = flatten(elements)
    element_groups = {}
    for element in elements:
        if key_type == 'Type':
            key = type(element)
        elif key_type == 'Category':
            for key in DB.BuiltInCategory.GetValues(DB.BuiltInCategory):
                if int(key) == element.Category.Id.IntegerValue:
                    break
        else:
            key = 'Unknown Key'
        if key not in element_groups:
            element_groups[key] = []
        element_groups[key].append(element)
    return element_groups

# working with parameters

def create_parameter_binding(doc, categories, is_type_binding=False):
    app = doc.Application
    category_set = app.Create.NewCategorySet()
    for category in to_list(categories):
        if isinstance(category, DB.BuiltInCategory):
            category = DB.Category.GetCategory(doc, category)
        category_set.Insert(category)
    if is_type_binding:
        return app.Create.NewTypeBinding(category_set)
    return app.Create.NewInstanceBinding(category_set)

def create_project_parameter(doc, external_definition, binding, p_group = DB.BuiltInParameterGroup.INVALID):
    if doc.ParameterBindings.Insert(external_definition, binding, p_group):
        iterator = doc.ParameterBindings.ForwardIterator()
        while iterator.MoveNext():
            internal_definition = iterator.Key
            parameter_element = doc.GetElement(internal_definition.Id)
            if isinstance(parameter_element, DB.SharedParameterElement) and parameter_element.GuidValue == external_definition.GUID:
                return internal_definition

def get_external_definition(app, group_name, definition_name):
    return app.OpenSharedParameterFile() \
        .Groups[group_name] \
        .Definitions[definition_name]

def get_parameter_value_v2(parameter):
    if isinstance(parameter, DB.Parameter):
        storage_type = parameter.StorageType
        if storage_type:
            exec 'parameter_value = parameter.As{}()'.format(storage_type)
            return parameter_value

# working with bounding boxes

def merge_bounding_boxes(bboxes):
    # type: (list) -> DB.BoundingBoxXYZ
    """Merges multiple bounding boxes"""
    merged_bb = DB.BoundingBoxXYZ()
    merged_bb.Min = DB.XYZ(
        min(bboxes, key=lambda bb: bb.Min.X).Min.X,
        min(bboxes, key=lambda bb: bb.Min.Y).Min.Y,
        min(bboxes, key=lambda bb: bb.Min.Z).Min.Z
    )
    merged_bb.Max = DB.XYZ(
        max(bboxes, key=lambda bb: bb.Max.X).Max.X,
        max(bboxes, key=lambda bb: bb.Max.Y).Max.Y,
        max(bboxes, key=lambda bb: bb.Max.Z).Max.Z
    )
    return merged_bb

def check_intersection(bbox, element):
    """Check if an element's bounding box intersects with the given bounding box."""
    outline = DB.Outline(bbox.Min, bbox.Max)
    filter_intersects = DB.BoundingBoxIntersectsFilter(outline, False)
    if element.get_BoundingBox(None) is not None:
        return filter_intersects.PassesFilter(doc, element.Id)
    return False

# working with solids

def get_all_solids(element, g_options, solids=None):
    '''retrieve all solids from elements'''
    if solids is None:
        solids = []
    if hasattr(element, "Geometry"):
        for item in element.Geometry[g_options]:
            get_all_solids(item, g_options, solids)
    elif isinstance(element, DB.GeometryInstance):
        for item in element.GetInstanceGeometry():
            get_all_solids(item, g_options, solids)
    elif isinstance(element, DB.Solid):
        solids.append(element)
    elif isinstance(element, DB.FamilyInstance):
        for item in element.GetSubComponentIds():
            family_instance = element.Document.GetElement(item)
            get_all_solids(family_instance, g_options, solids)
    return solids

def to_proto_type(elements, of_type=None):
    elements = flatten(elements) if of_type is None \
        else [item for item in flatten(elements) if isinstance(item, of_type)]
    proto_geometry = []
    for element in elements:
        if hasattr(element, 'ToPoint') and element.ToPoint():
            proto_geometry.append(element.ToPoint())
        elif hasattr(element, 'ToProtoType') and element.ToProtoType():
            proto_geometry.append(element.ToProtoType())
    return proto_geometry

# working with elements

def view_exists(doc, view_name):
    views = FEC(doc).OfClass(DB.View).ToElements()
    for view in views:
        if view.Name == view_name:
            return True
    return False

def get_3d_view_type_id(doc):
    collector = FEC(doc).OfClass(DB.ViewFamilyType)
    for view_type in collector:
        if view_type.ViewFamily == DB.ViewFamily.ThreeDimensional:
            return view_type.Id
    return None

def get_room_boundary(doc, item, options):
    e_list = []
    c_list = []
    try:
        for i in item.GetBoundarySegments(options):
            for j in i:
                e_list.append(doc.GetElement(j.ElementId))
                c_list.append(j.Curve.ToProtoType())
    except:
        calculator = DB.SpatialElementGeometryCalculator(doc)
        try:
            results = calculator.CalculateSpatialElementGeometry(item)
            for face in results.GetGeometry().Faces:
                for b_face in results.GetBoundaryFaceInfo(face):
                    e_list.append(doc.GetElement(b_face.SpatialBoundaryElement.HostElementId))
        except:
            pass
    return [e_list, c_list]

def get_mat_vol_area(doc, element):
    output_list = []
    no_mat_applied = []
    mat_ids = element.GetMaterialIds(False)
    if not mat_ids:
        no_material = element.Name + ', ' + element.Category.Name + ', ' + str(element.Id)
        no_mat_applied.append(no_material)
    else:
        for mat_id in mat_ids:
            material = doc.GetElement(mat_id).Name
            volume = unit_converter(doc, element.GetMaterialVolume(mat_id), to_internal=False, unit_type=DB.SpecTypeId.Volume)
            area = unit_converter(doc, element.GetMaterialArea(mat_id, False), to_internal=False, unit_type=DB.SpecTypeId.Area)
            output_list.append([material, volume, area])
    return list(set(no_mat_applied)) or output_list or None

def get_element_by_name(
        doc,
        name,
        element_class,
        family_name=None,
        return_all_elements=False):
    '''
    Получение элементов Revit по имени
    doc - документ Revit
    name - имя элемента
    element_class - класс элементов (обязательно наследник от Element)
    family_name - имя семейства
    return_all_elements - вернуть все найденные элементы
        False - возвращается лишь первый найденный элемент
        True - возвращается полный список найденных элементов
    '''
    elements = []
    for element in FEC(doc).OfClass(element_class):
        if DB.Element.Name.GetValue(element) != name:
            continue
        if family_name is not None:
            element_type = element if isinstance(element, DB.ElementType) \
                else doc.GetElement(element.GetTypeId())
            element_family_name = element_type.FamilyName if element_type \
                else None
            if element_family_name != family_name:
                continue
        elements.append(element)
    if elements:
        return elements if return_all_elements else elements[0]

class CategoriesSelectionFilter(SEL.ISelectionFilter):
    def __init__(self, b_categories):
        super(CategoriesSelectionFilter, self).__init__()
        self._category_ids = [DB.ElementId(b_category)
                              for b_category in to_list(b_categories)]

    def AllowElement(self, element):
        return element.Category.Id in self._category_ids
    

class RoomAntiRutinaField(object):
    """
    Антирутинное поле помещения. Расширяет базовый функционал помещения
    Revit и делает невозможным пребывание RuTINA в нем
    """
    def __init__(self, room):
        """Конструктор антирутинного поля помещения"""
        self._room = room

    @property
    def room(self):
        """Получить помещение, вокруг которого создано антирутинное поле"""
        return self._room

    @property
    def doc(self):
        """Получить документ с секретной информацией о помещении"""
        return self._room.Document

    @property
    def phase(self):
        """Понять, на какой стадии уничтожения RuTINA находится помещение"""
        return self.doc.GetElement(
            self._room.Parameter[DB.BuiltInParameter.ROOM_PHASE].AsElementId()
        )

    @property
    def name(self):
        """Получить имя помещения"""
        return self._room.Parameter(DB.BuiltInParameter.ROOM_NAME).AsString()

    @name.setter
    def name(self, room_name):
        """Задать имя помещения"""
        self._room.Parameter[DB.BuiltInParameter.ROOM_NAME].Set(room_name)

    @property
    def number(self):
        """Получить номер помещения"""
        return self._room.Number

    @number.setter
    def number(self, room_number):
        """Задать номер помещения"""
        self._room.Number = room_number

    @property
    def level(self):
        """Получить уровень, на котором расположено помещение"""
        return self._room.Level

    def _get_room_boundary_segments(self):
        """
        Получить сегменты контура помещения по чистовой внутренней грани стены
        в виде списка из списков объектов BoundarySegment (сегмент контура).

        Каждый список - это один замкнутый контур. Список под индексом 0 -
        внешний контур помещения. Под остальными индексами - внутренние.
        """
        return self._room.GetBoundarySegments(
            DB.SpatialElementBoundaryOptions()
        )

    def _get_boundary_segment_source_element(self, boundary_segment):
        """Получить исходный элемент, на основе которого сформирован
        тот или иной сегмент контура помещения"""
        return self.doc.GetElement(boundary_segment.ElementId)

    def _get_boundary_segment_wall_kind(self, boundary_segment):
        """Получить тип стены, на основе которой сформирован
        тот или иной сегмент контура помещения"""
        element = self._get_boundary_segment_source_element(boundary_segment)
        if element and hasattr(element, 'WallType'):
            return element.WallType.Kind

    def _get_wall_width(self, wall):
        """
        Получить толщину стены

        Для базовой стены функция возвращает значение свойства Width.
        Для витража - получает толщину (диаметр) каждого прямоугольного
        или круглого импоста и возвращает максимальное значение.
        """
        doc = self.doc
        wall_kind = wall.WallType.Kind
        if wall_kind == DB.WallKind.Basic:
            return wall.Width
        if wall_kind == DB.WallKind.Curtain:
            mullion_type_ids = set(
                [doc.GetElement(mullion_id).GetTypeId()
                 for mullion_id in wall.CurtainGrid.GetMullionIds()]
            )
            values = []
            for mullion_type_id in mullion_type_ids:
                mullion_type = doc.GetElement(mullion_type_id)
                width_parameter = mullion_type.Parameter[
                    DB.BuiltInParameter.RECT_MULLION_THICK]
                if width_parameter:
                    values.append(width_parameter.AsDouble())
                    continue
                radius_parameter = mullion_type.Parameter[
                    DB.BuiltInParameter.CIRC_MULLION_RADIUS]
                if radius_parameter:
                    values.append(radius_parameter.AsDouble() * 2)
            return max(values)

    def _create_curveloop(self,
                          boundary_segments,
                          curtain_segments_offset):
        """
        Создать объект CurveLoop на основе списка сегметов контура помещения.

        curtain_segments_offset - величина смещения сегментов витража;
        если None, то каждый сегмент витража будет смещен на половину толщины
        витража внутрь помещения;
        если 0, то контур будет получен по осевой линии витража;
        если положительное (отрицательное) значение, то все сегменты витража
        будут смещены на одинаковое расстояние внутрь (наружу) помещения;
        """
        curveloop = DB.CurveLoop.Create(
            [boundary_segment.GetCurve()
             for boundary_segment in boundary_segments]
        )
        if not(curtain_segments_offset or curtain_segments_offset is None):
            return curveloop
        offset_distances = []
        for boundary_segment in boundary_segments:
            offset = 0.0
            if self._get_boundary_segment_wall_kind(
                    boundary_segment) == DB.WallKind.Curtain:
                offset = curtain_segments_offset if curtain_segments_offset \
                    else self._get_wall_width(
                        self._get_boundary_segment_source_element(
                            boundary_segment)) / 2.0
            offset_distances.append(-float(offset))
        return DB.CurveLoop.CreateViaOffset(
            curveloop, offset_distances, DB.XYZ.BasisZ)

    def _get_room_boundaries(self, curtain_segments_offset):
        """
        Получить все контура помещения в виде списка из объектов CurveLoop.

        Каждый список - это один замкнутый контур. Список под индексом 0 -
        внешний контур помещения. Под остальными индексами - внутренние.
        curtain_segments_offset - величина смещения сегментов витража;
        """
        return [
            self._create_curveloop(boundary_segments, curtain_segments_offset)
            for boundary_segments in self._get_room_boundary_segments()
        ]

    def  _get_doors(self):
        doors = {
            'from': [],
            'to': []
        }
        room, phase = self._room, self.phase
        for door in FEC(self.doc).OfCategory(DB.BuiltInCategory.OST_Doors).WhereElementIsNotElementType():
            if door.get_BoundingBox(None) is None:
                continue
            from_room, to_room = door.FromRoom[phase], door.ToRoom[phase]
            if from_room and from_room.Id == room.Id:
                doors['from'].append(door)
            if to_room and to_room.Id == room.Id:
                doors['to'].append(door)
        return doors

    @property
    def from_room_doors(self):
        return self._get_doors()['from']

    @property
    def to_room_doors(self):
        return self._get_doors()['to']

    @property
    def doors(self):
        doors = []
        for key in 'from', 'to':
            doors.extend(self._get_doors()[key])
        return doors

    @property
    def door_ids(self):
        return List[DB.ElementId](door.Id for door in self.doors)
    
    def _get_door_width(self, door):
        wall_type = door.Host.WallType
        wall_kind = wall_type.Kind
        if wall_kind == DB.WallKind.Basic:
            return self.doc.GetElement(door.GetTypeId()).Parameter[DB.BuiltInParameter.FURNITURE_WIDTH].AsDouble()
        if wall_kind == DB.WallKind.Curtain:
            return door.Parameter[DB.BuiltInParameter.FURNITURE_WIDTH].AsDouble()

    def _get_door_origin(self, door):
        door_transform = door.GetTransform()
        return DB.XYZ(door_transform.Origin.X, door_transform.Origin.Y, door_transform.Origin.Z)
    
    def _get_room_to_door_direction(self, door):
        '''Get vector, that if perpendicular to room surfase, and directed to room'''
        to_room_direction = door.FacingOrientation
        if self._room.IsPointInRoom(self._get_door_origin(door) + to_room_direction * (self._get_wall_width(door.Host)/2)):
            return to_room_direction
        return -to_room_direction
    
    def _get_door_outline(self, door, door_depth, door_depth_ratio):
        '''Get horisontal door rectang, 0 < door depth < 1'''
        door_width = self._get_door_width(door)
        if door_width:
            half_door_width = door_width / 2.0
            hand_orientation = door.HandOrientation
            wall_width = self._get_wall_width(door.Host)
            origin = self._get_door_origin(door)
            if not door_depth > 0:
                door_depth = wall_width
            if 0 < door_depth_ratio < 1:
                door_depth *=door_depth_ratio
            if door_depth != wall_width:
                origin += self._get_room_to_door_direction(door) * ((wall_width - door_depth) / 2)
            return DB.CurveLoop.CreateViaThicken(DB.Line.CreateBound(
                origin + hand_orientation * half_door_width,
                origin - hand_orientation * half_door_width
            ), door_depth, DB.XYZ.BasisZ)

    def _add_door_outlines_via_solid_union(self, room_boundaries, doors_to_include, door_depth, door_depth_ratio):
        solid = DB.GeometryCreationUtilities.CreateExtrusionGeometry(
            room_boundaries,
            DB.XYZ.BasisZ,
            1
        )
        for door in doors_to_include:
            if door.Id in self.door_ids:
                DB.BooleanOperationsUtils.ExecuteBooleanOperationModifyingOriginalSolid(
                    solid,
                    DB.GeometryCreationUtilities.CreateExtrusionGeometry(
                        [self._get_door_outline(
                            door,
                            door_depth,
                            door_depth_ratio
                        )],
                    DB.XYZ.BasisZ,
                    1),
                    DB.BooleanOperationsType.Union
                )
        return solid.Faces[0].GetEdgesAsCurveLoops()

    def get_boundaries(self, curtain_segments_offset=None, doors_to_include=None, door_depth=None, door_depth_ratio=0.5):
        room_boundaries = self._get_room_boundaries(curtain_segments_offset)
        if doors_to_include is None:
            doors_to_include = self.doors
        if not doors_to_include:
            return room_boundaries
        return self._add_door_outlines_via_solid_union(room_boundaries, doors_to_include, door_depth, door_depth_ratio)

def create_direct_shape(doc, geometry_objects, category_id = DB.ElementId(DB.BuiltInCategory.OST_GenericModel)):
    direct_shape = DB.DirectShape.CreateElement(doc, category_id)
    direct_shape.SetShape(to_list(geometry_objects, DB.GeometryObject))
    return direct_shape