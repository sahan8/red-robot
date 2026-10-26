"""Builds the Red Robot from scratch: model, materials, rig, animations, baked AO, then saves the .blend and exports the .glb.

Run headless:  flatpak run org.blender.Blender -b --factory-startup --python scripts/build_robot.py
Blender 5.2. Units are metres, Z up, the robot faces -Y (glTF front, +Z in three.js), feet on the origin.
"""
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30
# Brand palette from the portfolio (index.css): red, ink, cream.
RED = (0.79, 0.012, 0.012)  # #e61919 in linear
INK = (0.0056, 0.0056, 0.0056)  # #111
CREAM = (0.9, 0.9, 0.86)  # #f4f4f0


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.unit_settings.system = 'METRIC'


# ---------- Materials ----------

def material(name, color, roughness, metallic=0.0, coat=0.0, emission=None, strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.use_backface_culling = True  # exported as single-sided: the browser skips faces nobody can see
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Coat Weight'].default_value = coat
    bsdf.inputs['Coat Roughness'].default_value = 0.08
    if emission:
        bsdf.inputs['Emission Color'].default_value = (*emission, 1)
        bsdf.inputs['Emission Strength'].default_value = strength
    return mat


def make_materials():
    return {
        # Painted metal: a clear coat over red gives the glossy toy-like highlight.
        'paint': material('RedPaint', RED, 0.38, coat=0.65),
        'rubber': material('InkRubber', INK, 0.62, metallic=0.15),
        'screen': material('CreamScreen', CREAM, 0.12, emission=CREAM, strength=0.35),
        'eye': material('InkGlass', INK, 0.05, coat=1.0),
        'light': material('RedLight', RED, 0.2, emission=(1, 0.05, 0.03), strength=4.0),
    }


# ---------- Geometry ----------

def finish(obj, mat, bevel=0.0, segments=3):
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new('Bevel', 'BEVEL')
        mod.width = bevel
        mod.segments = segments
        mod.limit_method = 'ANGLE'
        mod.harden_normals = True
    return obj


def box(name, size, loc, mat, bevel=0.03, bone=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = size
    bpy.ops.object.transform_apply(scale=True)
    obj['bone'] = bone
    return finish(obj, mat, bevel)


def cylinder(name, radius, depth, loc, mat, axis='Z', bone=None, verts=24, bevel=0.012):
    rot = {'X': (0, math.pi / 2, 0), 'Y': (math.pi / 2, 0, 0), 'Z': (0, 0, 0)}[axis]
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=depth, location=loc, rotation=rot)
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.transform_apply(rotation=True)
    obj['bone'] = bone
    return finish(obj, mat, bevel, 2)


def sphere(name, radius, loc, mat, bone=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=loc)
    obj = bpy.context.object
    obj.name = name
    bpy.ops.object.shade_smooth()
    obj['bone'] = bone
    return finish(obj, mat)


def letter(text, size, loc, mat, bone):
    """Extruded text in Blender's built-in font, turned to face the front and converted to a mesh."""
    bpy.ops.object.text_add(location=loc, rotation=(math.pi / 2, 0, 0))
    obj = bpy.context.object
    obj.data.body = text
    obj.data.size = size
    obj.data.extrude = 0.012
    obj.data.offset = 0.011  # thickens the thin built-in font into a bold mark
    obj.data.align_x, obj.data.align_y = 'CENTER', 'CENTER'
    bpy.ops.object.convert(target='MESH')
    obj = bpy.context.object
    bpy.ops.object.transform_apply(rotation=True)
    obj.name = f'Letter{text}'
    obj['bone'] = bone
    return finish(obj, mat)


def build_parts(m):
    parts = []
    add = parts.append
    for side, x in (('L', 1), ('R', -1)):
        # Legs
        add(box(f'Foot.{side}', (0.3, 0.44, 0.14), (0.2 * x, -0.05, 0.07), m['rubber'], 0.04, f'foot.{side}'))
        add(box(f'Toe.{side}', (0.26, 0.06, 0.06), (0.2 * x, -0.28, 0.04), m['paint'], 0.02, f'foot.{side}'))
        add(box(f'Shin.{side}', (0.21, 0.23, 0.4), (0.2 * x, 0, 0.36), m['paint'], 0.035, f'shin.{side}'))
        add(cylinder(f'Knee.{side}', 0.095, 0.24, (0.2 * x, 0, 0.58), m['rubber'], 'X', f'shin.{side}'))
        add(box(f'Thigh.{side}', (0.24, 0.26, 0.36), (0.2 * x, 0, 0.8), m['paint'], 0.04, f'thigh.{side}'))
        # Arms
        add(sphere(f'Shoulder.{side}', 0.13, (0.5 * x, 0, 1.66), m['rubber'], f'upperarm.{side}'))
        add(box(f'UpperArm.{side}', (0.18, 0.2, 0.34), (0.52 * x, 0, 1.43), m['paint'], 0.035, f'upperarm.{side}'))
        add(cylinder(f'Elbow.{side}', 0.085, 0.2, (0.52 * x, 0, 1.24), m['rubber'], 'X', f'forearm.{side}'))
        add(box(f'Forearm.{side}', (0.17, 0.19, 0.3), (0.52 * x, 0, 1.06), m['paint'], 0.035, f'forearm.{side}'))
        add(box(f'Hand.{side}', (0.17, 0.22, 0.17), (0.52 * x, 0, 0.82), m['rubber'], 0.05, f'hand.{side}'))
        add(box(f'Thumb.{side}', (0.07, 0.08, 0.14), (0.44 * x, -0.09, 0.88), m['rubber'], 0.025, f'hand.{side}'))
        # Head side "ears" with a red ring light
        add(cylinder(f'Ear.{side}', 0.11, 0.08, (0.43 * x, 0, 2.17), m['rubber'], 'X', 'head'))
        add(cylinder(f'EarLight.{side}', 0.05, 0.02, (0.475 * x, 0, 2.17), m['light'], 'X', 'head', 16, 0))
        add(box(f'Eye.{side}', (0.12, 0.03, 0.16), (0.14 * x, -0.342, 2.19), m['eye'], 0.035, 'eyes'))
        add(box(f'EyeShine.{side}', (0.03, 0.01, 0.035), (0.14 * x + 0.025, -0.36, 2.23), m['screen'], 0, 'eyes'))
        # Battery pack stripes
        add(box(f'PackStripe.{side}', (0.05, 0.02, 0.34), (0.12 * x, 0.405, 1.47), m['paint'], 0.01, 'chest'))

    add(box('Pelvis', (0.56, 0.36, 0.18), (0, 0, 1.03), m['rubber'], 0.04, 'hips'))
    add(box('Torso', (0.8, 0.5, 0.64), (0, 0, 1.45), m['paint'], 0.07, 'chest'))
    add(box('ChestPlate', (0.42, 0.03, 0.24), (0, -0.255, 1.52), m['screen'], 0.015, 'chest'))
    add(letter('S', 0.24, (0, -0.272, 1.52), m['paint'], 'chest'))
    add(box('BatteryPack', (0.5, 0.16, 0.46), (0, 0.32, 1.47), m['rubber'], 0.045, 'chest'))
    for i in range(3):  # vents under the chest plate
        add(box(f'Vent.{i}', (0.36, 0.02, 0.025), (0, -0.252, 1.32 - i * 0.05), m['rubber'], 0.008, 'chest'))
    add(sphere('StatusLight', 0.03, (0.3, -0.25, 1.68), m['light'], 'chest'))
    add(cylinder('Neck', 0.1, 0.14, (0, 0, 1.83), m['rubber'], 'Z', 'neck'))
    add(box('Head', (0.78, 0.64, 0.54), (0, 0, 2.17), m['paint'], 0.08, 'head'))
    add(box('Visor', (0.62, 0.04, 0.38), (0, -0.32, 2.16), m['screen'], 0.035, 'head'))
    add(box('Mouth', (0.1, 0.02, 0.022), (0, -0.342, 2.05), m['eye'], 0.008, 'head'))
    add(cylinder('AntennaStem', 0.018, 0.24, (0, 0, 2.55), m['rubber'], 'Z', 'antenna', 12, 0.004))
    add(sphere('AntennaTip', 0.05, (0, 0, 2.7), m['light'], 'antenna'))
    return parts


# ---------- Rig ----------

# name: (head, tail, parent)
BONES = {
    'root': ((0, 0, 0), (0, 0, 0.3), None),
    'hips': ((0, 0, 0.98), (0, 0, 1.12), 'root'),
    'spine': ((0, 0, 1.12), (0, 0, 1.4), 'hips'),
    'chest': ((0, 0, 1.4), (0, 0, 1.76), 'spine'),
    'neck': ((0, 0, 1.76), (0, 0, 1.9), 'chest'),
    'head': ((0, 0, 1.9), (0, 0, 2.44), 'neck'),
    'eyes': ((0, -0.34, 2.19), (0, -0.44, 2.19), 'head'),
    'antenna': ((0, 0, 2.44), (0, 0, 2.66), 'head'),
}
for _side, _x in (('L', 1), ('R', -1)):
    BONES.update({
        f'upperarm.{_side}': ((0.52 * _x, 0, 1.64), (0.52 * _x, 0, 1.24), 'chest'),
        f'forearm.{_side}': ((0.52 * _x, 0, 1.24), (0.52 * _x, 0, 0.92), f'upperarm.{_side}'),
        f'hand.{_side}': ((0.52 * _x, 0, 0.92), (0.52 * _x, 0, 0.74), f'forearm.{_side}'),
        f'thigh.{_side}': ((0.2 * _x, 0, 0.98), (0.2 * _x, 0, 0.58), 'hips'),
        f'shin.{_side}': ((0.2 * _x, 0, 0.58), (0.2 * _x, 0, 0.14), f'thigh.{_side}'),
        f'foot.{_side}': ((0.2 * _x, 0, 0.14), (0.2 * _x, -0.24, 0.1), f'shin.{_side}'),
    })


def build_rig():
    arm_data = bpy.data.armatures.new('RedRobotRig')
    rig = bpy.data.objects.new('RedRobotRig', arm_data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (head, tail, parent) in BONES.items():
        bone = arm_data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        bone.roll = 0
        if parent:
            bone.parent = arm_data.edit_bones[parent]
    bpy.ops.object.mode_set(mode='OBJECT')
    for pose_bone in rig.pose.bones:
        pose_bone.rotation_mode = 'XYZ'
    return rig


def skin(parts, rig):
    """Rigid skinning: every part follows exactly one bone. All parts become one mesh, so the robot is a single draw call per material."""
    for obj in parts:
        bpy.context.view_layer.objects.active = obj
        for mod in obj.modifiers:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        group = obj.vertex_groups.new(name=obj['bone'])
        group.add(range(len(obj.data.vertices)), 1.0, 'REPLACE')
    bpy.ops.object.select_all(action='DESELECT')
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    body = bpy.context.object
    body.name = 'RedRobot'
    body.parent = rig
    mod = body.modifiers.new('Rig', 'ARMATURE')
    mod.object = rig
    return body


# ---------- Animation ----------

def rad(degrees):
    return math.radians(degrees)


class Clip:
    """Keyframes pose-bone channels on one action. Angles in degrees; rotations are bone-local XYZ euler."""

    def __init__(self, rig, name, frames):
        self.rig, self.frames = rig, frames
        self.keyed = set()
        self.action = bpy.data.actions.new(name)
        self.action.use_fake_user = True
        rig.animation_data_create()
        rig.animation_data.action = self.action
        for pose_bone in rig.pose.bones:  # start every clip from the rest pose
            pose_bone.rotation_euler = (0, 0, 0)
            pose_bone.location = (0, 0, 0)
            pose_bone.scale = (1, 1, 1)

    def rot(self, bone, frame, x=0.0, y=0.0, z=0.0):
        pose_bone = self.rig.pose.bones[bone]
        pose_bone.rotation_euler = (rad(x), rad(y), rad(z))
        pose_bone.keyframe_insert('rotation_euler', frame=frame)
        self.keyed.add((bone, 'rotation_euler'))

    def loc(self, bone, frame, x=0.0, y=0.0, z=0.0):
        # Bone-local axes: for the vertical root bone local Y is world up.
        pose_bone = self.rig.pose.bones[bone]
        pose_bone.location = (x, y, z)
        pose_bone.keyframe_insert('location', frame=frame)
        self.keyed.add((bone, 'location'))

    def scale(self, bone, frame, x=1.0, y=1.0, z=1.0):
        pose_bone = self.rig.pose.bones[bone]
        pose_bone.scale = (x, y, z)
        pose_bone.keyframe_insert('scale', frame=frame)
        self.keyed.add((bone, 'scale'))

    def finish(self):
        """Keys every channel the clip leaves alone at its rest value, so no clip inherits the previous clip's pose (in Blender or in three.js)."""
        rest = {'rotation_euler': (0, 0, 0), 'location': (0, 0, 0), 'scale': (1, 1, 1)}
        for pose_bone in self.rig.pose.bones:
            for channel, value in rest.items():
                if (pose_bone.name, channel) not in self.keyed:
                    setattr(pose_bone, channel, value)
                    pose_bone.keyframe_insert(channel, frame=1)
        return self

    def cycle(self, bone, channel, values):
        """Spreads values evenly over the clip and closes the loop on the first value."""
        step = self.frames / len(values)
        for i, value in enumerate(values + values[:1]):
            frame = 1 + round(i * step)
            if channel == 'loc':
                self.loc(bone, frame, *value)
            else:
                self.rot(bone, frame, *value)


def blink(clip, at):
    clip.scale('eyes', at, 1, 1, 1)
    clip.scale('eyes', at + 2, 1, 1, 1)  # eyes bone points forward, so local X is width and local Z is height
    clip.scale('eyes', at + 4, 1, 1, 0.1)
    clip.scale('eyes', at + 7, 1, 1, 1)


def idle(rig):
    c = Clip(rig, 'Idle', 90)
    c.cycle('root', 'loc', [(0, 0, 0), (0, -0.012, 0)])
    c.cycle('chest', 'rot', [(0, 0, 1.5), (1.5, 0, 0), (0, 0, -1.5), (-1, 0, 0)])
    c.cycle('head', 'rot', [(0, 0, -3), (2, 0, 0), (0, 0, 3), (-2, 0, 0)])
    for side, s in (('L', 1), ('R', -1)):
        c.cycle(f'upperarm.{side}', 'rot', [(-3, 0, -6 * s), (3, 0, -8 * s)])
        c.cycle(f'forearm.{side}', 'rot', [(-8, 0, 0), (-12, 0, 0)])
    c.cycle('antenna', 'rot', [(4, 0, 0), (-4, 0, 0), (3, 0, 0), (-3, 0, 0)])
    blink(c, 55)
    return c


def walk(rig, name='Walk', frames=32, stride=28, lift=55, swing=24, bob=0.05, lean=4):
    c = Clip(rig, name, frames)
    # Contact, down, passing, up — then the mirror for the other leg.
    c.cycle('root', 'loc', [(0, 0, 0), (0, -bob, 0), (0, bob * 0.6, 0), (0, 0, 0), (0, -bob, 0), (0, bob * 0.6, 0)])
    c.cycle('spine', 'rot', [(lean, 0, 5), (lean, 0, 0), (lean, 0, -5), (lean, 0, 0)])
    c.cycle('head', 'rot', [(-lean, 0, -4), (-lean, 0, 0), (-lean, 0, 4), (-lean, 0, 0)])
    legs = {'L': [(-stride, 0, 0), (-stride * 0.4, 0, 0), (stride * 0.6, 0, 0), (stride, 0, 0), (0, 0, 0), (-stride * 0.8, 0, 0)],
            'R': None}
    legs['R'] = legs['L'][3:] + legs['L'][:3]
    for side in ('L', 'R'):
        c.cycle(f'thigh.{side}', 'rot', legs[side])
        knee = [(0, 0, 0), (12, 0, 0), (8, 0, 0), (10, 0, 0), (lift, 0, 0), (lift * 0.5, 0, 0)]
        c.cycle(f'shin.{side}', 'rot', knee if side == 'L' else knee[3:] + knee[:3])
        foot = [(-12, 0, 0), (0, 0, 0), (8, 0, 0), (14, 0, 0), (-10, 0, 0), (-16, 0, 0)]
        c.cycle(f'foot.{side}', 'rot', foot if side == 'L' else foot[3:] + foot[:3])
    for side, s in (('L', 1), ('R', -1)):
        arm = [(swing, 0, -5 * s), (-swing, 0, -5 * s)] if side == 'L' else [(-swing, 0, -5 * s), (swing, 0, -5 * s)]
        c.cycle(f'upperarm.{side}', 'rot', arm)
        c.cycle(f'forearm.{side}', 'rot', [(-15 - swing * 0.6, 0, 0), (-15, 0, 0)])
    return c


def run(rig):
    return walk(rig, 'Run', frames=20, stride=45, lift=95, swing=55, bob=0.09, lean=14)


def jump(rig):
    c = Clip(rig, 'Jump', 44)
    poses = [  # frame, root height, thigh, shin, foot, upperarm, forearm, spine
        (1, 0.0, 0, 0, 0, 0, -10, 0),
        (10, -0.22, -50, 85, -35, 35, -30, 18),   # crouch
        (15, 0.15, 5, 5, 10, -160, -10, -6),      # launch, arms up
        (22, 0.75, -35, 70, 0, -150, -30, 0),     # tuck at the top
        (29, 0.25, -10, 20, 15, -60, -20, 4),     # reach for the floor
        (33, -0.18, -45, 80, -30, 20, -40, 16),   # land
        (44, 0.0, 0, 0, 0, 0, -10, 0),
    ]
    for frame, height, thigh, shin, foot, upper, fore, spine in poses:
        c.loc('root', frame, 0, height, 0)
        c.rot('spine', frame, spine)
        c.rot('head', frame, -spine * 0.5)
        for side, s in (('L', 1), ('R', -1)):
            c.rot(f'thigh.{side}', frame, thigh)
            c.rot(f'shin.{side}', frame, shin)
            c.rot(f'foot.{side}', frame, foot)
            c.rot(f'upperarm.{side}', frame, upper, 0, -12 * s)
            c.rot(f'forearm.{side}', frame, fore)
    blink(c, 12)
    return c


def wave(rig):
    c = Clip(rig, 'Wave', 60)
    # Right arm (robot's right, screen left) swings up and out, the forearm waves three times.
    c.rot('upperarm.R', 1, 0, 0, 6)
    for frame in (10, 52):
        c.rot('upperarm.R', frame, -20, 0, 150)
    c.rot('upperarm.R', 60, 0, 0, 6)
    c.rot('forearm.R', 1, -10)
    for i, frame in enumerate(range(12, 50, 6)):
        c.rot('forearm.R', frame, -10, 0, 30 if i % 2 else -25)
    c.rot('forearm.R', 60, -10)
    c.rot('upperarm.L', 1, 0, 0, -6)
    c.rot('upperarm.L', 60, 0, 0, -6)
    c.rot('head', 1)
    c.rot('head', 12, 0, -10, 6)
    c.rot('head', 50, 0, -10, 6)
    c.rot('head', 60)
    c.rot('chest', 1)
    c.rot('chest', 14, 0, -5, 0)
    c.rot('chest', 50, 0, -5, 0)
    c.rot('chest', 60)
    blink(c, 30)
    return c


def dance(rig):
    c = Clip(rig, 'Dance', 48)
    c.cycle('root', 'loc', [(0.06, -0.08, 0), (0, 0, 0), (-0.06, -0.08, 0), (0, 0, 0)])
    c.cycle('hips', 'rot', [(0, 0, 10), (0, 0, 0), (0, 0, -10), (0, 0, 0)])
    c.cycle('chest', 'rot', [(0, -8, -10), (0, 0, 0), (0, 8, 10), (0, 0, 0)])
    c.cycle('head', 'rot', [(8, 10, 0), (-6, 0, 0), (8, -10, 0), (-6, 0, 0)])
    c.cycle('upperarm.L', 'rot', [(-30, 0, -150), (-10, 0, -40), (-20, 0, -70), (-10, 0, -40)])
    c.cycle('upperarm.R', 'rot', [(-20, 0, 70), (-10, 0, 40), (-30, 0, 150), (-10, 0, 40)])
    c.cycle('forearm.L', 'rot', [(-20, 0, 0), (-80, 0, 0), (-60, 0, 0), (-80, 0, 0)])
    c.cycle('forearm.R', 'rot', [(-60, 0, 0), (-80, 0, 0), (-20, 0, 0), (-80, 0, 0)])
    for side in ('L', 'R'):
        c.cycle(f'thigh.{side}', 'rot', [(-20, 0, 0), (0, 0, 0)])
        c.cycle(f'shin.{side}', 'rot', [(35, 0, 0), (0, 0, 0)])
        c.cycle(f'foot.{side}', 'rot', [(-15, 0, 0), (0, 0, 0)])
    c.cycle('antenna', 'rot', [(0, 0, 12), (0, 0, -12)])
    return c


def thumbs_up(rig):
    c = Clip(rig, 'ThumbsUp', 50)
    up = ((-50, 0, 14), -55, 90, 6)
    for frame, upper, fore, hand, head in ((1, (0, 0, 6), -10, 0, 0), (12, *up), (40, *up), (50, *up)):
        c.rot('upperarm.R', frame, *upper)
        c.rot('forearm.R', frame, fore)
        c.rot('hand.R', frame, 0, hand, 0)
        c.rot('head', frame, -head, -8 if head else 0, 4 if head else 0)
    c.rot('chest', 1)
    c.rot('chest', 12, -4, -6, 0)
    c.rot('chest', 50, -4, -6, 0)
    c.rot('upperarm.L', 1, 0, 0, -6)
    c.rot('upperarm.L', 50, 0, 0, -6)
    blink(c, 30)
    return c


def nod(rig):
    c = Clip(rig, 'Yes', 36)
    for frame, tilt in ((1, 0), (7, 16), (13, -4), (19, 14), (25, -3), (36, 0)):
        c.rot('head', frame, tilt)
        c.rot('neck', frame, tilt * 0.3)
    blink(c, 20)
    return c


def sit(rig):
    c = Clip(rig, 'Sit', 30)
    for frame, drop, thigh, shin, arm in ((1, 0, 0, 0, 0), (18, -0.45, -95, 95, -30), (30, -0.4, -90, 90, -25)):
        c.loc('root', frame, 0, drop, 0)
        c.rot('spine', frame, -abs(arm) * 0.15)
        for side, s in (('L', 1), ('R', -1)):
            c.rot(f'thigh.{side}', frame, thigh, 0, 4 * s)
            c.rot(f'shin.{side}', frame, shin)
            c.rot(f'upperarm.{side}', frame, arm, 0, -10 * s)
            c.rot(f'forearm.{side}', frame, arm)
    return c


CLIPS = [idle, walk, run, jump, wave, dance, thumbs_up, nod, sit]


def animate(rig):
    clips = [make(rig).finish() for make in CLIPS]
    # Looping is the player's job (three.js LoopRepeat); each looping clip already ends on its first pose.
    # Keep every clip on its own NLA track so the exporter writes each one as a separate glTF animation.
    rig.animation_data.action = None
    for clip in clips:
        track = rig.animation_data.nla_tracks.new()
        track.name = clip.action.name
        strip = track.strips.new(clip.action.name, 1, clip.action)
        track.mute = True
    return clips


# ---------- Bake ----------

def bake_ao(body, size=1024, samples=96):
    """Bakes ambient occlusion into one texture shared by every material, wired as the glTF occlusion map."""
    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.006)
    bpy.ops.object.mode_set(mode='OBJECT')

    image = bpy.data.images.new('RedRobot_AO', size, size)
    gltf_group = gltf_output_group()
    for mat in body.data.materials:
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        tex = nodes.new('ShaderNodeTexImage')
        tex.image = image
        tex.name = 'AO'
        nodes.active = tex
        out = nodes.new('ShaderNodeGroup')
        out.node_tree = gltf_group
        sep = nodes.new('ShaderNodeSeparateColor')
        links.new(tex.outputs['Color'], sep.inputs['Color'])
        links.new(sep.outputs['Red'], out.inputs['Occlusion'])

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    scene.render.bake.margin = 8
    # Bake in the rest pose with the armature off, so the occlusion matches the mesh the browser skins.
    body.modifiers['Rig'].show_render = False
    bpy.ops.object.bake(type='AO')
    body.modifiers['Rig'].show_render = True
    image.filepath_raw = os.path.join(ROOT, 'export', 'red-robot-ao.png')
    image.file_format = 'PNG'
    image.save()
    return image


def gltf_output_group():
    """The glTF exporter reads occlusion from a node group named 'glTF Material Output' with an 'Occlusion' input."""
    group = bpy.data.node_groups.get('glTF Material Output')
    if group:
        return group
    group = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree')
    group.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
    group.nodes.new('NodeGroupInput')
    return group


# ---------- Export ----------

def export(rig, body):
    os.makedirs(os.path.join(ROOT, 'export'), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'red-robot.blend'))
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True)
    body.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(ROOT, 'export', 'red-robot.glb'),
        export_format='GLB',
        use_selection=True,
        export_animations=True,
        export_animation_mode='NLA_TRACKS',
        export_force_sampling=True,
        export_frame_step=1,
        export_image_format='WEBP',
        export_image_quality=82,
        export_apply=False,
        export_yup=True,
    )


def main():
    reset()
    mats = make_materials()
    parts = build_parts(mats)
    rig = build_rig()
    body = skin(parts, rig)
    animate(rig)
    if '--no-bake' not in sys.argv:
        bake_ao(body)
    export(rig, body)
    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    print(f'RED_ROBOT_OK tris={tris} actions={[a.name for a in bpy.data.actions]}')


main()
