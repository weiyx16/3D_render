## --- use::
## add a text in blender and copy it into with a run command
## This code is for render a SMPL on a random image.

import bpy
import random as rd 
import math
import os
from mathutils import Matrix, Vector, Quaternion, Euler
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

def my_mkdir(directory):
    try:
        os.makedirs(directory)
    except FileExistsError:
        pass

# create the different passes that we render
def create_composite_nodes(tree, img=None):
    
    # clear default nodes
    for n in tree.nodes:
        tree.nodes.remove(n)

    # create node for foreground image
    layers = tree.nodes.new('CompositorNodeRLayers')
    layers.location = -300, 400

    # create node for background image
    bg_im = tree.nodes.new('CompositorNodeImage')
    bg_im.location = -300, 30
    if img is not None:
        bg_im.image = img

    # create node for mixing foreground and background images 
    mix = tree.nodes.new('CompositorNodeMixRGB')
    mix.location = 40, 30
    mix.use_alpha = True

    # create node for the final output 
    composite_out = tree.nodes.new('CompositorNodeComposite')
    composite_out.location = 240, 30

    # merge fg and bg images
    tree.links.new(bg_im.outputs[0], mix.inputs[1])
    tree.links.new(layers.outputs['Image'], mix.inputs[2])
    tree.links.new(mix.outputs[0], composite_out.inputs[0])            # bg+fg image

def create_sh_material(tree, sh_path, img=None):
    # clear default nodes
    for n in tree.nodes:
        tree.nodes.remove(n)


    # TODO how to solve the image problem

    # osl 
    script = tree.nodes.new('ShaderNodeScript')
    script.location = -230, 400
    script.mode = 'EXTERNAL'
    script.filepath = sh_path #'spher_harm/sh.osl' #using the same file from multiple jobs causes white texture
    script.update()

    # attribute
    attri = tree.nodes.new('ShaderNodeAttribute')
    attri.location = -230, -100
    attri.attribute_name = 'Col'

    # diffuse bsdf
    diffu = tree.nodes.new('ShaderNodeBsdfDiffuse')
    diffu.location = 0, -100

    # mix shader?
    mixshader = tree.nodes.new('ShaderNodeMixShader')
    mixshader.location = 300, 300

    # add shader?
    addshader = tree.nodes.new('ShaderNodeAddShader')
    addshader.location = 300, 100

    # light path
    light = tree.nodes.new('ShaderNodeLightPath')
    light.location = 100, 600

    # the emission node makes it independent of the scene lighting
    emission = tree.nodes.new('ShaderNodeEmission')
    emission.location = 0, 200
    emission.inputs[1].default_value = 1 # o.1
    emission.inputs[0].default_value = (1,1,1,1) # the color value can also be set in sh.osl

    mat_out = tree.nodes.new('ShaderNodeOutputMaterial')
    mat_out.location = 500, 400

    tree.links.new(script.outputs[0], emission.inputs[0])
    tree.links.new(attri.outputs[0], diffu.inputs[0])
    tree.links.new(diffu.outputs[0], mixshader.inputs[1])
    tree.links.new(emission.outputs[0], mixshader.inputs[2])
    tree.links.new(light.outputs[2], mixshader.inputs[0])
    tree.links.new(mixshader.outputs[0], mat_out.inputs[0])

def init_scene(SCENE, smpl_name):

    obj = bpy.data.objects[smpl_name]
    obj.data.use_auto_smooth = False
    obj.active_material = bpy.data.materials['Material'] # assign the existing spherical harmonics material

    scene = bpy.context.scene

    # set camera properties and initial position
    cam_data = bpy.data.cameras.new("Camera")
    bpy.data.objects.new(name="Camera", object_data=cam_data)

    bpy.ops.object.select_all(action='DESELECT')
    cam_obj = bpy.data.objects['Camera']
    scene.objects.active = cam_obj
    scene.objects.link(cam_obj)  # instance the camera object in the scene
    scene.camera = cam_obj       # set the active camera

    # TODO the camera location`
    cam_obj.location = 3.2, -1.9, 0.5
    cam_obj.select = True 
    cam_obj.rotation_euler = (1.4,0,65)
    '''
    camera_distance = np.random.normal(10.0, 1)
    cam_obj.matrix_world = Matrix(((0., 0., 1, camera_distance),
                                 (0., -1, 0., -1.0),
                                 (-1., 0., 0., 0.),
                                 (0.0, 0.0, 0.0, 1.0)))
    cam_obj.data.angle = math.radians(40)
    cam_obj.data.lens =  60
    cam_obj.data.clip_start = 0.1
    cam_obj.data.sensor_width = 32
    cam_obj.rotation_euler = (0,0,0.14)
    '''
    '''
    cam_data = bpy.data.cameras.new("MyCam")
    cam_ob = bpy.data.objects.new(name="MyCam", object_data=cam_data)
    scene.objects.link(cam_ob)  # instance the camera object in the scene
    scene.camera = cam_ob       # set the active camera
    '''


    # Lamp
    lamp_data = bpy.data.lamps.new("Lamp", 'POINT')
    lamp_ob = bpy.data.objects.new(name="Lamp", object_data=lamp_data)
    scene.objects.link(lamp_ob)
    lamp_ob.location = 3.2, -1.9, 0.5

    
    scene.cycles.film_transparent = True
    scene.render.layers["RenderLayer"].use_pass_vector = True
    scene.render.layers["RenderLayer"].use_pass_normal = True
    SCENE.render.layers['RenderLayer'].use_pass_emit  = True
    SCENE.render.layers['RenderLayer'].use_pass_material_index  = True

    scene.render.resolution_x = 450
    scene.render.resolution_y = 338
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'

    return obj, cam_obj

def render_function(save_path, background_path, smpl_path):

    # Clear existing objects.
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # bpy.context.window.screen = bpy.data.screens['Default']
    SCENE = bpy.data.scenes['Scene']
    ## !! use osl must in cycles
    SCENE.render.engine = 'CYCLES'
    SCENE.cycles.shading_system = True
    SCENE.use_nodes = True

    bpy.data.materials.new("Material")
    bpy.data.materials['Material'].use_nodes = True

    bg_img = bpy.data.images.load(filepath=background_path,check_existing=False)
    # texture_path = '/home/weiyx/Desktop/tex.png'
    # tex_img = bpy.data.images.load(filepath=texture_path,check_existing=False)

    # if smpl_path:
    bpy.ops.import_mesh.ply(filepath=smpl_path)
    _ , smpl_name = os.path.split(smpl_path)
    ## use when the blender need't the extension
    smpl_name = smpl_name[0:-4]
    

    # bpy.data.objects[smpl_name].location = -(get center)
    # random rotation the smpl
    '''
    random_angle = [(rd.random()-0.5)*math.pi for i in range(3)]
    bpy.data.objects[smpl_name].rotation_euler = random_angle
    '''

    # ------------------- relightingt test
    mat_tree = bpy.data.materials['Material'].node_tree
    # sh_dst = join(save_path, 'sh.osl')
    sh_dst = '/home/weiyx/Desktop/sh.osl'  
    create_sh_material(mat_tree, sh_dst)

    create_composite_nodes(SCENE.node_tree, img=bg_img)

    obj, cam_obj = init_scene(SCENE, smpl_name)

    setState0()
    obj.select = True
    bpy.context.scene.objects.active = obj
    materials = {'FullBody': bpy.data.materials['Material']}

    scs = []
    for mname, material in materials.items():
        scs.append(material.node_tree.nodes['Script'])
        scs[-1].filepath = sh_dst
        scs[-1].update()

    SCENE.node_tree.nodes['Image'].image = bg_img

    # random light
    sh_coeffs = .7 * (2 * np.random.rand(9) - 1)
    sh_coeffs[0] = .5 + .9 * np.random.rand() # Ambient light (first coeff) needs a minimum  is ambient. Rest is uniformly distributed, higher means brighter.
    sh_coeffs[1] = -.7 * np.random.rand()

    for ish, coeff in enumerate(sh_coeffs):
        for sc in scs:
            sc.inputs[ish+1].default_value = coeff

    # render the image TODO
    save_file_name = smpl_name + '.png'
    blend_save_path = save_path
    save_path = save_path + save_file_name
    SCENE.render.use_antialiasing = False
    SCENE.render.filepath = save_path
   
    # disable render output
    logfile = '/dev/null'
    open(logfile, 'a').close()
    old = os.dup(1)
    sys.stdout.flush()
    os.close(1)
    os.open(logfile, os.O_WRONLY)

    # Render
    bpy.ops.render.render(write_still=True)

    # disable output redirection
    os.close(1)
    os.dup(old)
    os.close(old)

    # bpy.ops.wm.save_as_mainfile(filepath=join(blend_save_path, 'test.blend'))

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
    background_path = '/home/weiyx/Desktop/2.png'
    smpl_path = '/home/weiyx/Desktop/smpl_tex.ply'

    
    render_function(save_path, background_path, smpl_path)
    print("batch job finished, exiting")


if __name__ == "__main__":
    main()
