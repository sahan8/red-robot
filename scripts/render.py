"""Renders stills of the Red Robot from red-robot.blend: a hero still, or a pose sheet of every clip.

flatpak run org.blender.Blender -b /path/red-robot.blend --python scripts/render.py -- <mode> <out> [engine]
  mode: still | sheet | turntable | showreel
"""
import math
import os
import sys

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
MODE = args[0] if args else 'still'
OUT = args[1] if len(args) > 1 else '/tmp/red-robot'
ENGINE = args[2] if len(args) > 2 else 'BLENDER_EEVEE'
BG = (0.905, 0.9, 0.87)  # the site's cream #f4f4f0 in linear-ish

scene = bpy.context.scene
rig = bpy.data.objects['RedRobotRig']


def setup(width, height, transparent=False):
    scene.render.engine = ENGINE
    if ENGINE == 'CYCLES':
        scene.cycles.samples = 48
        scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.film_transparent = transparent
    # Standard sRGB, like three.js output: AgX would wash the brand red out to salmon.
    scene.view_settings.view_transform = 'Standard'
    world = bpy.data.worlds.new('Studio')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (*BG, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.6
    scene.world = world
    # Three-point studio light, matching the site's key-from-top-right setup.
    for name, loc, energy, size in (('Key', (3, -4, 5), 900, 3), ('Fill', (-4, -3, 2.5), 300, 4), ('Rim', (0, 4, 4), 600, 2)):
        light = bpy.data.lights.new(name, 'AREA')
        light.energy, light.size = energy, size
        obj = bpy.data.objects.new(name, light)
        scene.collection.objects.link(obj)
        obj.location = loc
        obj.rotation_euler = (Vector((0, 0, 1.3)) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    # Shadow catcher floor
    bpy.ops.mesh.primitive_plane_add(size=30)
    floor = bpy.context.object
    floor.is_shadow_catcher = True
    mat = bpy.data.materials.new('Floor')
    mat.use_nodes = True
    mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (*BG, 1)
    mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 1
    floor.data.materials.append(mat)


def camera(distance=7.5, height=1.4, target=1.3, lens=50, yaw=-18):
    cam_data = bpy.data.cameras.new('Cam')
    cam_data.lens = lens
    cam = bpy.data.objects.new('Cam', cam_data)
    scene.collection.objects.link(cam)
    a = math.radians(yaw)
    cam.location = (math.sin(a) * distance, -math.cos(a) * distance, height)
    cam.rotation_euler = (Vector((0, 0, target)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    scene.camera = cam
    return cam


def play(name, frame):
    track_action = bpy.data.actions[name]
    rig.animation_data.action = track_action
    for track in rig.animation_data.nla_tracks:
        track.mute = True
    scene.frame_set(frame)


def action_length(name):
    return int(bpy.data.actions[name].frame_range[1])


if MODE == 'still':
    setup(1036, 1404, transparent=True)
    camera(distance=8.2, height=1.6, target=1.3, yaw=-16)
    play('Idle', 1)
    scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)

elif MODE == 'poster':
    # The portfolio hero's placeholder: same framing as RobotJourney.jsx (orthographic, robot fills 92% of the height,
    # soles 4% above the bottom, tilted 0.12 rad toward the camera), transparent, 0.55 wide so the arms fit.
    setup(440, 800, transparent=True)
    bpy.data.objects.remove(bpy.data.objects['Plane'])
    cam = camera()
    cam.data.type = 'ORTHO'
    height = 2.75 / 0.92
    cam.data.ortho_scale = height  # ortho_scale spans the longer side, here the height
    centre = height / 2 - 0.04 * height
    cam.location = (0, -20 * math.cos(0.12), centre + 20 * math.sin(0.12))
    cam.rotation_euler = (math.pi / 2 - 0.12, 0, 0)
    play('Idle', 1)
    scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)

elif MODE == 'pose':
    # pose <out> <engine> <clip> <frame> <yaw>: one close-up for checking details.
    setup(720, 900)
    camera(distance=6.5, height=1.7, target=1.45, yaw=float(args[5]))
    play(args[3], int(args[4]))
    scene.render.filepath = OUT
    bpy.ops.render.render(write_still=True)

elif MODE == 'sheet':
    # One small render per (clip, phase); stitched into a grid afterwards with ffmpeg.
    setup(360, 420)
    camera(distance=8.5, height=1.5, target=1.25, yaw=-28)
    os.makedirs(OUT, exist_ok=True)
    for name in ['Idle', 'Walk', 'Run', 'Jump', 'Wave', 'Dance', 'ThumbsUp', 'Yes', 'Sit']:
        length = action_length(name)
        for i, t in enumerate((0.0, 0.25, 0.5, 0.75)):
            play(name, 1 + round(t * (length - 1)))
            scene.render.filepath = os.path.join(OUT, f'{name}_{i}.png')
            bpy.ops.render.render(write_still=True)

elif MODE == 'turntable':
    setup(720, 720)
    cam = camera(distance=8.0, height=1.6, target=1.3)
    os.makedirs(OUT, exist_ok=True)
    play('Idle', 1)
    for i, yaw in enumerate(range(0, 360, 45)):
        a = math.radians(yaw)
        cam.location = (math.sin(a) * 8, -math.cos(a) * 8, 1.6)
        cam.rotation_euler = (Vector((0, 0, 1.3)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
        scene.render.filepath = os.path.join(OUT, f'turn_{i}.png')
        bpy.ops.render.render(write_still=True)

elif MODE == 'showreel':
    # Every clip back to back (looping clips twice), slowly orbiting; frames are encoded to MP4 afterwards.
    setup(1280, 720)
    cam = camera(distance=8.4, height=1.6, target=1.3, lens=45)
    os.makedirs(OUT, exist_ok=True)
    n = 0
    loops = {'Idle': 1, 'Walk': 3, 'Run': 4, 'Dance': 2}
    for name in ['Idle', 'Wave', 'Walk', 'Run', 'Jump', 'Dance', 'ThumbsUp', 'Yes', 'Sit']:
        length = action_length(name)
        for frame in list(range(1, length + 1)) * loops.get(name, 1):
            a = math.radians(-35 + n * 0.12)
            cam.location = (math.sin(a) * 8.4, -math.cos(a) * 8.4, 1.6)
            cam.rotation_euler = (Vector((0, 0, 1.3)) - cam.location).to_track_quat('-Z', 'Y').to_euler()
            play(name, frame)
            scene.render.filepath = os.path.join(OUT, f'f{n:05d}.png')
            bpy.ops.render.render(write_still=True)
            n += 1
    print('SHOWREEL_FRAMES', n)
