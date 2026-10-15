import os
import sys
import math
import argparse
import datetime
import struct
import numpy as np

# Shadery uproszczone; lista odniesienia:
# https://assettocorsamods.net/threads/assetto-corsa-shaders-texture-maps-list.794/


def cli():
    # Konsola Windows (cp1250) nie zna emoji z komunikatów – zamiast wyjątku podmień znak
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Specify the path to the .kn5 model directory.")
    args = parser.parse_args()
    target_dir = os.path.abspath(args.path)

    print(target_dir)

    if not os.path.exists(target_dir):
        print("The model directory doesn't exist")
        raise SystemExit(1)

    # Filter by .kn5 extension
    extension = ".kn5"

    # List all files in the folder with the specified extension
    files = [os.path.join(target_dir, file) for file in os.listdir(target_dir) if file.endswith(extension)]

    # Convert each file
    for file in files:
        convert_to_obj(file)


class kn5Material:
    def __init__(self):
        self.name = ""
        self.shader = ""
        self.ksAmbient = 0.6
        self.ksDiffuse = 0.6
        self.ksSpecular = 0.9
        self.ksSpecularEXP = 1.0
        self.diffuseMult = 1.0
        self.normalMult = 1.0
        self.useDetail = 0.0
        self.detailUVMultiplier = 1.0
        self.txDiffuse = ""
        self.txNormal = ""
        self.txDetail = ""
        self.txDetailR = ""
        self.txDetailG = ""
        self.txDetailB = ""
        self.txDetailA = ""
        self.txDetailNM = ""
        self.txMask = ""
        self.shader_props = ""
        # not implemented...
        self.ksEmissive = 0.0
        self.ksAlphaRef = 1.0


class kn5Node:
    def __init__(self):
        self.name = "Default"
        self.parent = None
        self.tmatrix = np.identity(4)
        self.hmatrix = np.identity(4)
        self.meshIndex = -1
        self.type = 1
        self.materialID = -1
        self.translation = np.identity(3)
        self.rotation = np.identity(3)
        self.scaling = np.identity(3)
        self.vertexCount = 0
        self.indices = []
        self.position = []
        self.normal = []
        self.texture0 = []


def read_string(file, length):
    data = file.read(length)
    return data.decode("utf-8")


def matrix_mult(ma, mb):
    return np.matmul(np.array(ma, copy=True), np.array(mb, copy=True))


def matrix_to_euler(transf):
    heading = 0
    attitude = 0
    bank = 0

    # left-handed
    if (transf[0][1] > 0.998):
        heading = np.arctan2(-transf[1][0], transf[1][1])
        attitude = -math.pi / 2
        bank = 0.0
    elif (transf[0][1] < -0.998):
        heading = np.arctan2(-transf[1][0], transf[1][1])
        attitude = math.pi / 2
        bank = 0.0
    else:
        heading = np.arctan2(transf[0][1], transf[0][0])
        bank = np.arctan2(transf[1][2], transf[2][2])
        attitude = np.arcsin(-transf[0][2])

    attitude *= 180 / math.pi
    heading *= 180 / math.pi
    bank *= 180 / math.pi

    return [bank, attitude, heading]


def scale_from_matrix(transf):
    scaleX = math.sqrt(transf[0][0] ** 2 + transf[1][0] ** 2 + transf[2][0] ** 2)
    scaleY = math.sqrt(transf[0][1] ** 2 + transf[1][1] ** 2 + transf[2][1] ** 2)
    scaleZ = math.sqrt(transf[0][2] ** 2 + transf[1][2] ** 2 + transf[2][2] ** 2)
    return [float(scaleX), float(scaleY), float(scaleZ)]


def read_nodes(file, node_list, parent_id):
    new_node = kn5Node()
    new_node.parent = parent_id

    new_node.type, = struct.unpack('<i', file.read(4))
    new_node.name = read_string(file, struct.unpack('<i', file.read(4))[0])
    children_count, = struct.unpack('<i', file.read(4))
    _ = file.read(1)  # abyte

    if new_node.type == 1:  # dummy
        new_node.tmatrix = [[0] * 4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                new_node.tmatrix[i][j], = struct.unpack('<f', file.read(4))

        new_node.translation = [new_node.tmatrix[3][0],
                                new_node.tmatrix[3][1],
                                new_node.tmatrix[3][2]]
        new_node.rotation = matrix_to_euler(new_node.tmatrix)
        new_node.scaling = scale_from_matrix(new_node.tmatrix)

    elif new_node.type == 2:  # mesh
        file.read(3)  # bbyte, cbyte, dbyte
        new_node.vertexCount, = struct.unpack('<i', file.read(4))
        new_node.position = []
        new_node.normal = []
        new_node.texture0 = []

        for _ in range(new_node.vertexCount):
            new_node.position.extend(struct.unpack('<fff', file.read(12)))
            new_node.normal.extend(struct.unpack('<fff', file.read(12)))
            tex = struct.unpack('<ff', file.read(8))
            tex = (tex[0], 1.0 - tex[1])
            new_node.texture0.extend(tex)
            file.read(12)  # tangents

        index_count, = struct.unpack('<i', file.read(4))
        new_node.indices = struct.unpack('<%dH' % index_count, file.read(index_count * 2))
        new_node.materialID, = struct.unpack('<i', file.read(4))
        file.read(29)

    elif new_node.type == 3:  # animated mesh
        file.read(3)  # bbyte, cbyte, dbyte
        bone_count, = struct.unpack('<i', file.read(4))
        for _ in range(bone_count):
            _ = read_string(file, struct.unpack('<i', file.read(4))[0])  # bone_name
            file.read(64)  # bone matrix

        new_node.vertexCount, = struct.unpack('<i', file.read(4))
        new_node.position = []
        new_node.normal = []
        new_node.texture0 = []
        for _ in range(new_node.vertexCount):
            new_node.position.extend(struct.unpack('<fff', file.read(12)))
            new_node.normal.extend(struct.unpack('<fff', file.read(12)))
            tex = struct.unpack('<ff', file.read(8))
            tex = (tex[0], 1.0 - tex[1])
            new_node.texture0.extend(tex)
            file.read(44)  # tangents & weights

        index_count, = struct.unpack('<i', file.read(4))
        new_node.indices = struct.unpack('<%dH' % index_count, file.read(index_count * 2))
        new_node.materialID, = struct.unpack('<i', file.read(4))
        file.read(12)

    if parent_id < 0:
        new_node.hmatrix = new_node.tmatrix
    else:
        new_node.hmatrix = matrix_mult(new_node.tmatrix, node_list[parent_id].hmatrix)

    node_list.append(new_node)
    current_id = len(node_list) - 1

    for _ in range(children_count):
        node_list = read_nodes(file, node_list, current_id)

    return node_list


def transparant_shader(shader) -> bool:
    if shader.startswith("ksPerPixelAT"):
        return True
    if shader in ('ksPerPixelAlpha', 'ksSkidMark', 'ksTree', 'ksGrass', 'ksFlags'):
        return True
    return False


def _sanitize_name(name: str) -> str:
    return name.replace(' ', '_')


def export_obj(model_name, output_dir, materials: list[kn5Material], nodes: list[kn5Node]):
    model_filename = model_name

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    skip_ac_nodes = True

    # --- MTL ---
    print('Exporting MTL...')
    with open(os.path.join(output_dir, model_filename + '.mtl'), 'w', encoding="utf-8") as mtl_writer:
        mtl_str = ''
        for src_mat in materials:
            mtl_str += f'newmtl {_sanitize_name(src_mat.name)}\r\n'
            mtl_str += f'Ka {src_mat.ksAmbient} {src_mat.ksAmbient} {src_mat.ksAmbient}\r\n'
            mtl_str += f'Kd {src_mat.ksDiffuse} {src_mat.ksDiffuse} {src_mat.ksDiffuse}\r\n'
            mtl_str += f'Ks {src_mat.ksSpecular} {src_mat.ksSpecular} {src_mat.ksSpecular}\r\n'
            mtl_str += f'Ns {src_mat.ksSpecularEXP}\r\n'
            mtl_str += 'illum 2\r\n'

            is_transparent = transparant_shader(src_mat.shader)
            if is_transparent:
                mtl_str += 'd 0.9999\r\n'

            # mapy
            if src_mat.useDetail == 1.0 and src_mat.txDetail:
                mtl_str += f'map_Kd texture\\{src_mat.txDetail}\r\n'
                if src_mat.txDiffuse:
                    mtl_str += f'map_Ks texture\\{src_mat.txDiffuse}\r\n'
                if is_transparent and src_mat.txDetailA:
                    mtl_str += f'map_d texture\\{src_mat.txDetailA}\r\n'
            elif src_mat.txDiffuse:
                mtl_str += f'map_Kd texture\\{src_mat.txDiffuse}\r\n'
                if is_transparent:
                    mtl_str += f'map_d texture\\{src_mat.txDiffuse}\r\n'

            if src_mat.txNormal:
                mtl_str += f'bump texture\\{src_mat.txNormal}\r\n'

            mtl_str += '\r\n'

        mtl_writer.write(mtl_str)

    # --- Jeden OBJ z wieloma grupami (POPRAWNE OFFSEty) ---
    print(f"Exporting meshes into single OBJ: {model_filename}.obj")
    obj_path = os.path.join(output_dir, model_filename + ".obj")

    vertex_offset = 0  # globalny offset dla v/vt/vn
    with open(obj_path, "w", encoding="utf-8") as OBJwriter:
        sb_header = "# Assetto Corsa model\n"
        sb_header += f"# Exported on {datetime.datetime.now()}\n"
        sb_header += f"mtllib {model_filename}.mtl\n\n"
        OBJwriter.write(sb_header)

        for srcNode in nodes:
            if skip_ac_nodes and srcNode.name.startswith("AC_"):
                continue
            if srcNode.type not in [2, 3]:
                continue

            # grupa i materiał
            OBJwriter.write(f"o {_sanitize_name(srcNode.name)}\n")
            if srcNode.materialID >= 0:
                OBJwriter.write(f"usemtl {_sanitize_name(materials[srcNode.materialID].name)}\n")

            # Wierzchołki – zastosuj hmatrix (transformacje)
            for v in range(srcNode.vertexCount):
                x = srcNode.position[v * 3]
                y = srcNode.position[v * 3 + 1]
                z = srcNode.position[v * 3 + 2]
                vx = srcNode.hmatrix[0][0] * x + srcNode.hmatrix[1][0] * y + srcNode.hmatrix[2][0] * z + srcNode.hmatrix[3][0]
                vy = srcNode.hmatrix[0][1] * x + srcNode.hmatrix[1][1] * y + srcNode.hmatrix[2][1] * z + srcNode.hmatrix[3][1]
                vz = srcNode.hmatrix[0][2] * x + srcNode.hmatrix[1][2] * y + srcNode.hmatrix[2][2] * z + srcNode.hmatrix[3][2]
                OBJwriter.write(f"v {vx} {vy} {vz}\n")

            # Normale – bez translacji (tylko 3x3)
            for v in range(srcNode.vertexCount):
                x = srcNode.normal[v * 3]
                y = srcNode.normal[v * 3 + 1]
                z = srcNode.normal[v * 3 + 2]
                nx = srcNode.hmatrix[0][0] * x + srcNode.hmatrix[1][0] * y + srcNode.hmatrix[2][0] * z
                ny = srcNode.hmatrix[0][1] * x + srcNode.hmatrix[1][1] * y + srcNode.hmatrix[2][1] * z
                nz = srcNode.hmatrix[0][2] * x + srcNode.hmatrix[1][2] * y + srcNode.hmatrix[2][2] * z
                OBJwriter.write(f"vn {nx} {ny} {nz}\n")

            # UV z mnożnikiem materiału
            UVmult = 1.0
            if srcNode.materialID >= 0:
                mat = materials[srcNode.materialID]
                UVmult = mat.diffuseMult if mat.useDetail == 0.0 else mat.detailUVMultiplier

            for v in range(srcNode.vertexCount):
                tx = srcNode.texture0[v * 2] * UVmult
                ty = srcNode.texture0[v * 2 + 1] * UVmult
                OBJwriter.write(f"vt {tx} {ty}\n")

            # Trójkąty z poprawnymi offsetami
            for i in range(0, len(srcNode.indices), 3):
                i1 = srcNode.indices[i] + 1 + vertex_offset
                i2 = srcNode.indices[i + 1] + 1 + vertex_offset
                i3 = srcNode.indices[i + 2] + 1 + vertex_offset
                OBJwriter.write(f"f {i1}/{i1}/{i1} {i2}/{i2}/{i2} {i3}/{i3}/{i3}\n")

            vertex_offset += srcNode.vertexCount
            OBJwriter.write("\n")

    print(f"✅ Exported single OBJ: {obj_path}")


def read_kn5(file_path, output_dir):
    textures = []
    materials = []
    meshes = []

    if not os.path.exists(output_dir):
        os.mkdir(output_dir)

    with open(file_path, "rb") as file:
        header = file.read(10)
        magic, version = struct.unpack("<6s1I", header)

        if version > 5:
            _ = file.read(4)

        # Textures
        tex_count = struct.unpack("<i", file.read(4))[0]
        for _ in range(tex_count):
            tex_type = struct.unpack("<i", file.read(4))[0]  # unused
            tex_name = read_string(file, struct.unpack("<i", file.read(4))[0])
            tex_size = struct.unpack("<i", file.read(4))[0]
            textures.append(tex_name)

            tex_path = os.path.join(output_dir, "texture", tex_name)
            if os.path.exists(tex_path):
                file.seek(tex_size, os.SEEK_CUR)
            else:
                os.makedirs(os.path.dirname(tex_path), exist_ok=True)
                with open(tex_path, "wb") as tex_file:
                    tex_file.write(file.read(tex_size))

        # Materials
        mat_count = struct.unpack("<i", file.read(4))[0]
        for _ in range(mat_count):
            new_material = kn5Material()
            new_material.name = read_string(file, struct.unpack("<i", file.read(4))[0])
            new_material.shader = read_string(file, struct.unpack("<i", file.read(4))[0])
            _ashort = struct.unpack("<h", file.read(2))[0]
            if version > 4:
                _azero = struct.unpack("<i", file.read(4))[0]

            prop_count = struct.unpack("<i", file.read(4))[0]
            for _ in range(prop_count):
                prop_name = read_string(file, struct.unpack("<i", file.read(4))[0])
                prop_value = struct.unpack("<f", file.read(4))[0]
                new_material.shader_props += prop_name + " = " + str(prop_value) + "&cr;&lf;"

                if prop_name == "ksAmbient":
                    new_material.ksAmbient = prop_value
                elif prop_name == "ksDiffuse":
                    new_material.ksDiffuse = prop_value
                elif prop_name == "ksSpecular":
                    new_material.ksSpecular = prop_value
                elif prop_name == "ksSpecularEXP":
                    new_material.ksSpecularEXP = prop_value
                elif prop_name == "diffuseMult":
                    new_material.diffuseMult = prop_value
                elif prop_name == "normalMult":
                    new_material.normalMult = prop_value
                elif prop_name == "useDetail":
                    new_material.useDetail = prop_value
                elif prop_name == "detailUVMultiplier":
                    new_material.detailUVMultiplier = prop_value
                elif prop_name == "ksEmissive":
                    new_material.ksEmissive = prop_value
                elif prop_name == "ksAlphaRef":
                    new_material.ksAlphaRef = prop_value

                file.seek(36, os.SEEK_CUR)

            tex_slots = struct.unpack("<i", file.read(4))[0]
            for _ in range(tex_slots):
                sample_name = read_string(file, struct.unpack("<i", file.read(4))[0])
                sample_slot = struct.unpack("<i", file.read(4))[0]  # unused
                tex_name = read_string(file, struct.unpack("<i", file.read(4))[0])

                new_material.shader_props += sample_name + " = " + tex_name + "&cr;&lf;"

                if sample_name == "txDiffuse":
                    new_material.txDiffuse = tex_name
                elif sample_name == "txNormal":
                    new_material.txNormal = tex_name
                elif sample_name == "txDetail":
                    new_material.txDetail = tex_name
                elif sample_name == "txDetailR":
                    new_material.txDetailR = tex_name
                elif sample_name == "txDetailG":
                    new_material.txDetailG = tex_name
                elif sample_name == "txDetailB":
                    new_material.txDetailB = tex_name
                elif sample_name == "txDetailA":
                    new_material.txDetailA = tex_name
                elif sample_name == "txDetailNM":
                    new_material.txDetailNM = tex_name
                elif sample_name == "txMask":
                    new_material.txMask = tex_name

            materials.append(new_material)

        # Nodes (meshes)
        meshes = read_nodes(file, meshes, -1)

        return textures, materials, meshes


def convert_to_obj(file_path):
    model_name = os.path.splitext(os.path.basename(file_path))[0]
    output_dir = os.path.join(os.path.dirname(file_path), "output")

    _, materials, meshes = read_kn5(file_path, output_dir)
    export_obj(model_name, output_dir, materials, meshes)


if __name__ == "__main__":
    cli()
    # file = "./models/daytona_2017/daytonagroove.kn5"
    # convert_to_obj(file)
