## --- use::
## add a text in blender and copy it into with a run command
## This code is for render a SMPL on a random image.

import bpy
import random as rd 
import math
import os
import mathutils
import time
from os.path import join, dirname, realpath, exists
import sys       # to get command line args
import argparse  # to parse options for us and print a nice help message
import numpy as np
'''
start_time = None
def log_message(message):
    elapsed_time = time.time() - start_time
    print("[%.2f s] %s" % (elapsed_time, message))
'''
def setState0():
    for ob in bpy.data.objects.values():
        ob.select=False
    bpy.context.scene.objects.active = None
    # Clear existing objects.
    bpy.ops.wm.read_factory_settings(use_empty=True)

def my_mkdir(directory):
    try:
        os.makedirs(directory)
    except FileExistsError:
        pass

def create_sh_material(tree, sh_path, img=None):
    # clear default nodes
    for n in tree.nodes:
        tree.nodes.remove(n)

    uv = tree.nodes.new('ShaderNodeTexCoord')
    uv.location = -800, 400

    uv_xform = tree.nodes.new('ShaderNodeVectorMath')
    uv_xform.location = -600, 400
    uv_xform.inputs[1].default_value = (0, 0, 1)
    uv_xform.operation = 'AVERAGE'

    uv_im = tree.nodes.new('ShaderNodeTexImage')
    uv_im.location = -400, 400
    if img is not None:
        uv_im.image = img

    rgb = tree.nodes.new('ShaderNodeRGB')
    rgb.location = -400, 200

    script = tree.nodes.new('ShaderNodeScript')
    script.location = -230, 400
    script.mode = 'EXTERNAL'
    script.filepath = sh_path #'spher_harm/sh.osl' #using the same file from multiple jobs causes white texture
    script.update()

    # the emission node makes it independent of the scene lighting
    emission = tree.nodes.new('ShaderNodeEmission')
    emission.location = -60, 400

    mat_out = tree.nodes.new('ShaderNodeOutputMaterial')
    mat_out.location = 110, 400

    tree.links.new(uv.outputs[2], uv_im.inputs[0])
    tree.links.new(uv_im.outputs[0], script.inputs[0])
    tree.links.new(script.outputs[0], emission.inputs[0])
    tree.links.new(emission.outputs[0], mat_out.inputs[0])


def render_function(save_path, background_path, smpl_path):

    # Clear existing objects.
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # bpy.context.window.screen = bpy.data.screens['Default']
    scene = bpy.context.scene
    ## !! use osl must in cycles
    scene.render.engine = 'CYCLES'
    scene.cycles.shading_system = True
    scene.use_nodes = True

    # if smpl_path:
    bpy.ops.import_scene.obj(filepath=smpl_path)
    _ , smpl_name = os.path.split(smpl_path)
    ## use when the blender need't the extension
    smpl_name = smpl_name[0:-4]

    # random rotation the smpl
    '''
    random_angle = [(rd.random()-0.5)*math.pi for i in range(3)]
    bpy.data.objects[smpl_name].rotation_euler = random_angle
    '''

    # ------------------- relightingt test
    print("Building materials tree")
    bpy.data.materials.new("Material")
    bpy.data.materials['Material'].use_nodes = True
    mat_tree = bpy.data.materials['Material'].node_tree
    # sh_dst = join(save_path, 'sh.osl')
    sh_dst = '/home/weiyx/Desktop/sh.osl'
    materials = {'FullBody': bpy.data.materials['Material']}
    create_sh_material(mat_tree, sh_dst)

    scs = []
    for mname, material in materials.items():
        scs.append(material.node_tree.nodes['Script'])
        scs[-1].filepath = sh_dst
        scs[-1].update()

    # random light
    sh_coeffs = .7 * (2 * np.random.rand(9) - 1)
    sh_coeffs[0] = .5 + .9 * np.random.rand() # Ambient light (first coeff) needs a minimum  is ambient. Rest is uniformly distributed, higher means brighter.
    sh_coeffs[1] = -.7 * np.random.rand()

    for ish, coeff in enumerate(sh_coeffs):
        for sc in scs:
            sc.inputs[ish+1].default_value = coeff

    # assign the existing spherical harmonics material
    bpy.data.objects[smpl_name].active_material = bpy.data.materials['Material']
    
    # -------------------

    # if background_path:
    # bg_dir, bg_name = os.path.split(background_path)

    img = bpy.data.images.load(filepath=background_path,check_existing=False)
    rv3d = None
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                space_data = area.spaces.active
                rv3d = space_data.region_3d
                space_data.show_background_images = True
                bg = space_data.background_images.new()
                bg.image = img
                break
    # scene.node_tree.nodes['Image'].image = img
    # read image size
    # bpy.data.scenes["scene"].render.resolution_x = 
    # bpy.data.scenes["scene"].render.resolution_y =

    # set camera properties and initial position
    # bpy.ops.object.select_all(action='DESELECT')
    cam_data = bpy.data.cameras.new("MyCam")
    cam_ob = bpy.data.objects.new(name="MyCam", object_data=cam_data)
    scene.objects.link(cam_ob)  # instance the camera object in the scene
    scene.camera = cam_ob       # set the active camera
    # scene.objects.active = cam_ob
    cam_ob.location = 4.5, -3, 1.0
    cam_ob.select = True 
    cam_ob.rotation_euler = (1.4,0,1)
    '''TODO
    camera_distance = np.random.normal(8.0, 1)

    cam_ob.matrix_world = Matrix(((0., 0., 1, camera_distance),
                                 (0., -1, 0., -1.0),
                                 (-1., 0., 0., 0.),
                                 (0.0, 0.0, 0.0, 1.0)))
    cam_ob.data.angle = math.radians(40)
    cam_ob.data.lens =  60
    cam_ob.data.clip_start = 0.1
    cam_ob.data.sensor_width = 32
    '''
    rv3d.view_perspective = 'CAMERA' # Go to camera perspective to see your BG iamge

    # add material to the smpl and set diffuse
    # Can't assign materials in editmode
    # bpy.ops.object.mode_set(mode='OBJECT')
    if len(bpy.data.objects[smpl_name].material_slots) < 1:
        # if there is no slot then we append to create the slot and assign
        mat_smpl = bpy.data.materials.new("Material")
        # mat_smpl.diffuse_color = rd.random(), rd.random(), rd.random()
        mat_smpl.diffuse_color = 0.5,0.5,0.5
        bpy.data.objects[smpl_name].data.materials.append(mat_smpl)
        bpy.data.objects[smpl_name].data.materials["Material"].specular_intensity = 0

    else:
        # we always want the material in slot[0]
        bpy.data.objects[smpl_name].material_slots[0].material = bpy.data.materials['Material']

    # bpy.context.space_data.context = 'TEXTURE'
    bpy.data.textures.new("Texture",'IMAGE')
    img_texture = bpy.data.images.load(filepath=background_path,check_existing=False)
    bpy.data.textures["Texture"].image = img_texture

    # bpy.context.space_data.context = 'WORLD'
    if scene.world is None:
        # create a new world
        new_world = bpy.data.worlds.new("New World")
        new_world.use_sky_paper = True
        scene.world = new_world
        slot = scene.world.texture_slots.add()
        slot.use_map_horizon = True
        ## important to use this
        slot.texture = bpy.data.textures["Texture"]
        # scene.world.texture_slots[0].use_map_horizon = True
       
    # render the image
    save_file_name = smpl_name + '.png'
    save_path = save_path + save_file_name

    bpy.data.scenes['Scene'].render.filepath = save_path
    bpy.ops.render.render( write_still=True ) 
    # if save_path:
    # save the rendered image
    print('Render over')

def main():
    
    '''
    global start_time
    start_time = time.time()

    argv = sys.argv

    if "--" not in argv:
        argv = []  # as if no args are passed
    else:
        argv = argv[argv.index("--") + 1:]  # get all args after "--"

    # When --help or no args are given, print this help
    usage_text = (
            "Run this script in background of blender"
            "Generate the synthetic images"
            )

    parser = argparse.ArgumentParser(description=usage_text)

    # input the arguments needed

    parser.add_argument("-s", "--save", dest="save_path", metavar='FILE',
            help="Save the generated file to the specified path")
    parser.add_argument("-bg", "--bground", dest="background_path", metavar='FILE',
            help="Read the background file from the specified path")
    parser.add_argument("-smpl", "--smpl", dest="smpl_path", metavar='FILE',
            help="Read the smpl file from the specified path")

    args = parser.parse_args(argv)  # In this example we wont use the args

    log_message("input save_path: %s" % args.save_path)
    log_message("input background_path: %s" % args.background_path)
    log_message("input smpl_path: %s" % args.smpl_path)

    if not argv:
        parser.print_help()
        return

    if not args.save_path or not args.background_path or not args.smpl_path:
        print("Error: some arguments are not given, aborting.")
        parser.print_help()
        return
    
    if not exists(save_path):
        my_mkdir(save_path)

    ## TODO if we really need the tmp_path
    tmp_path = join(tmp_path, 'run%d_%s_c%04d' % (runpass, name.replace(" ", ""), (ishape + 1)))
    params['tmp_path'] = tmp_path
    
    # check if already computed
    #  + clean up existing tmp folders if any
    if exists(tmp_path) and tmp_path != "" and tmp_path != "/":
        os.system('rm -rf %s' % tmp_path)

    # create tmp directory
    if not exists(tmp_path):
        my_mkdir(tmp_path)
    
    ## TODO or use the config file?

    ## TODO the sh_dir??? why need it?
    # create copy-spher.harm. directory if not exists
    sh_dir = join(tmp_path, 'spher_harm')
    if not exists(sh_dir):
        my_mkdir(sh_dir)
    sh_dst = join(sh_dir, 'sh_%02d_%05d.osl' % (runpass, idx))
    os.system('cp spher_harm/sh.osl %s' % sh_dst)

    # TODO use:
    # in the init_scene also find: 

    log_message("Building materials tree")
    bpy.data.materials['Material'].use_nodes = True
    mat_tree = bpy.data.materials['Material'].node_tree
    create_sh_material(mat_tree, sh_dst, cloth_img)
    res_paths = create_composite_nodes(scene.node_tree, params, img=bg_img, idx=idx)
    # ----before init the sense

    ## TODO random image input:
    log_message("Listing background images")
    bg_names = join(bg_path, '%s_img.txt' % idx_info['use_split'])
    nh_txt_paths = []
    with open(bg_names) as f:
        for line in f:
            nh_txt_paths.append(join(bg_path, line))

    # random background
    bg_img_name = choice(nh_txt_paths)[:-1]
    bg_img = bpy.data.images.load(bg_img_name)

    # Run the example function
    # render_function(args.save_path, args.render_path, args.background_path, args.smpl_path)
    '''

    save_path = '/home/weiyx/Desktop/'
    background_path = '/home/weiyx/Desktop/1.png'
    smpl_path = '/home/weiyx/Desktop/hello_smpl.obj'

    
    render_function(save_path, background_path, smpl_path)
    print("batch job finished, exiting")


if __name__ == "__main__":
    main()
