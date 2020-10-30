#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
TODOS
=====

* Something more elegant for joints synthesized from multiple joints
'''

import glob
import math
from openni import openni2, nite2, utils
import pygame
import random
import subprocess
import sys
import time

SHOW_FPS = False
DEBUG_NO_KINECT = False

IDLE_IMAGE_TIMEOUT_S = 5
FADE_LENGTH_S = 1

CAPTURE_SIZE_KINECT = (512, 424)
CAPTURE_SIZE_OTHERS = (640, 480)

# Assumed display aspect ratio - pygame doesn't detect multiple displays
# so we assume a wide-screen main display
ASPECT_RATIO = 16 / 9
FULL_SCREEN = True
WINDOWED_WIDTH = 960
WINDOWED_HEIGHT = 540
MIRRORED = False
KINECT_ANGLE = 15

# Empirically measured min and max values in depth space.
# x range: -101.86 to 730
# y range: -291.67 to 677.72
# Values are outside of the view range probably because the position of limbs is extrapolated,
# so give a bit of extra rendering space and shift points over to compensate
DEPTH_SPACE_WIDTH = 840
DEPTH_SPACE_HEIGHT = 840
DEPTH_SPACE_X_ADJUST = 100
DEPTH_SPACE_Y_ADJUST = 100

RESET_TIMEOUT_S = 3

BODYPART_LIST = {
    'left-femur': {
        'joints': (nite2.JointType.NITE_JOINT_LEFT_HIP, nite2.JointType.NITE_JOINT_LEFT_KNEE),
        'coords': ((64, 18), (32, 330)),
    },
    'left-lower-arm-and-hand': {
        'joints': (nite2.JointType.NITE_JOINT_LEFT_ELBOW, nite2.JointType.NITE_JOINT_LEFT_HAND),
        'coords': ((62, 5), (62, 211)),
    },
    'left-shin-and-foot': {
        'joints': (nite2.JointType.NITE_JOINT_LEFT_KNEE, nite2.JointType.NITE_JOINT_LEFT_FOOT),
        'coords': ((72, 16), (47, 308)),
    },
    'left-upper-arm': {
        'joints': (nite2.JointType.NITE_JOINT_LEFT_SHOULDER, nite2.JointType.NITE_JOINT_LEFT_ELBOW),
        'coords': ((30, 20), (31, 237))
    },
    'pelvis': {
        'joints': (nite2.JointType.NITE_JOINT_LEFT_HIP, nite2.JointType.NITE_JOINT_RIGHT_HIP),
        'coords': ((29, 50), (177, 50))
    },
    'ribcage': {
        'joints': (nite2.JointType.NITE_JOINT_NECK, (nite2.JointType.NITE_JOINT_LEFT_HIP, nite2.JointType.NITE_JOINT_RIGHT_HIP)),
        'coords': ((164, 1), (164, 354)),
    },
    'right-femur': {
        'joints': (nite2.JointType.NITE_JOINT_RIGHT_HIP, nite2.JointType.NITE_JOINT_RIGHT_KNEE),
        'coords': ((16, 19), (48, 330)),
    },
    'right-lower-arm-and-hand': {
        'joints': (nite2.JointType.NITE_JOINT_RIGHT_ELBOW, nite2.JointType.NITE_JOINT_RIGHT_HAND),
        'coords': ((61, 5), (61, 211)),
    },
    'right-shin-and-foot': {
        'joints': (nite2.JointType.NITE_JOINT_RIGHT_KNEE, nite2.JointType.NITE_JOINT_RIGHT_FOOT),
        'coords': ((29, 16), (55, 308)),
    },
    'right-upper-arm': {
        'joints': (nite2.JointType.NITE_JOINT_RIGHT_SHOULDER, nite2.JointType.NITE_JOINT_RIGHT_ELBOW),
        'coords': ((32, 18), (29, 237)),
    },
    'skull':  {
        'joints': (nite2.JointType.NITE_JOINT_HEAD, nite2.JointType.NITE_JOINT_NECK),
        'coords': ((63, 98), (63, 219)),
    },
}


class BodyPart(pygame.sprite.Sprite):
    def __init__(self, name, joints, joint_coords):
        pygame.sprite.Sprite.__init__(self)
        self.name = name
        self.joints = joints
        self.joint_coords = joint_coords
        if len(joints) == 2:
            joint_vector = (joint_coords[0][0] - joint_coords[1][0], joint_coords[0][1] - joint_coords[1][1])
            self.joint_length = math.sqrt(sum(v**2 for v in joint_vector))
            self.angle_orig = self.get_angle(joint_coords[0][0], joint_coords[0][1], joint_coords[1][0], joint_coords[1][1])

        filename = 'skeleton-images/{}.png'.format(self.name)
        self.image_orig = pygame.image.load(filename)
        self.rect_orig = self.image_orig.get_rect()
        self.image = self.image_orig
        self.rect = self.image.get_rect()

    def get_angle(self, x1, y1, x2, y2):
        theta = math.atan2(y2 - y1, x2 - x1)
        theta = 2 * math.pi + theta if theta < 0 else theta
        angle = 360 - (theta * 360 / (2 * math.pi) - 90)
        return angle

    def get_rotated_origin(self, image, pos, originPos, angle):
        # see: https://stackoverflow.com/questions/4183208/how-do-i-rotate-an-image-around-its-center-using-pygame

        # calcaulate the axis aligned bounding box of the rotated image
        w, h       = image.get_size()
        box        = [pygame.math.Vector2(p) for p in [(0, 0), (w, 0), (w, -h), (0, -h)]]
        box_rotate = [p.rotate(angle) for p in box]
        min_box    = (min(box_rotate, key=lambda p: p[0])[0], min(box_rotate, key=lambda p: p[1])[1])
        max_box    = (max(box_rotate, key=lambda p: p[0])[0], max(box_rotate, key=lambda p: p[1])[1])

        # calculate the translation of the pivot
        pivot        = pygame.math.Vector2(originPos[0], -originPos[1])
        pivot_rotate = pivot.rotate(angle)
        pivot_move   = pivot_rotate - pivot

        # calculate the upper left origin of the rotated image
        origin = (pos[0] - originPos[0] + min_box[0] - pivot_move[0], pos[1] - originPos[1] - max_box[1] + pivot_move[1])
        origin_int = (int(origin[0]), int(origin[1]))
        return origin_int

    def update(self, user_tracker, user):
        j1confident = False
        j2confident = False
        if len(self.joints) == 2:
            if type(self.joints[0]) is tuple:
                j1a = user.skeleton.joints[self.joints[0][0]]
                j1b = user.skeleton.joints[self.joints[0][1]]
                (x1a, y1a) = user_tracker.convert_joint_coordinates_to_depth(j1a.position.x, j1a.position.y, j1a.position.z)
                (x1b, y1b) = user_tracker.convert_joint_coordinates_to_depth(j1b.position.x, j1b.position.y, j1b.position.z)
                (x1, y1) = (x1a + (x1b - x1a) / 2, y1a + (y1b - y1a) / 2)
                if (0.4 < j1a.positionConfidence and 0.4 < j1b.positionConfidence):
                    j1confident = True
            else :
                j1 = user.skeleton.joints[self.joints[0]]
                (x1, y1) = user_tracker.convert_joint_coordinates_to_depth(j1.position.x, j1.position.y, j1.position.z)
                if (0.4 < j1.positionConfidence):
                    j1confident = True
            if type(self.joints[1]) is tuple:
                j2a = user.skeleton.joints[self.joints[1][0]]
                j2b = user.skeleton.joints[self.joints[1][1]]
                (x2a, y2a) = user_tracker.convert_joint_coordinates_to_depth(j2a.position.x, j2a.position.y, j2a.position.z)
                (x2b, y2b) = user_tracker.convert_joint_coordinates_to_depth(j2b.position.x, j2b.position.y, j2b.position.z)
                (x2, y2) = (x2a + (x2b - x2a) / 2, y2a + (y2b - y2a) / 2)
                if (0.4 < j2a.positionConfidence and 0.4 < j2b.positionConfidence):
                    j2confident = True
            else :
                j2 = user.skeleton.joints[self.joints[1]]
                (x2, y2) = user_tracker.convert_joint_coordinates_to_depth(j2.position.x, j2.position.y, j2.position.z)
                if (0.4 < j2.positionConfidence):
                    j2confident = True
        if j1confident or j2confident:
            self.x1_last = x1
            self.y1_last = y1
            self.x2_last = x2
            self.y2_last = y2
            joint_vector = (x1 - x2, y1 - y2)
            joint_length = math.sqrt(sum(v**2 for v in joint_vector))
            scale = joint_length / self.joint_length
            joint_angle = self.get_angle(x1, y1, x2, y2)
            angle = joint_angle - self.angle_orig

            width_scaled = int(self.rect_orig[2] * scale)
            height_scaled = int(self.rect_orig[3] * scale)
            if width_scaled > 0 and height_scaled > 0:
                scaled_image = pygame.transform.smoothscale(self.image_orig, (width_scaled, height_scaled))
                origin = (self.joint_coords[0][0] * scale, self.joint_coords[0][1] * scale)
                rotated_origin = self.get_rotated_origin(scaled_image, (x1, y1), origin, angle)
                self.image = pygame.transform.rotate(scaled_image, angle)
                self.rect = self.image.get_rect()
                self.rect.x = rotated_origin[0] + DEPTH_SPACE_X_ADJUST
                self.rect.y = rotated_origin[1] + DEPTH_SPACE_Y_ADJUST

class IdleImage(pygame.sprite.Sprite):
    def __init__(self, filename):
        pygame.sprite.Sprite.__init__(self)
        self.filename = filename
        self.image = pygame.image.load(filename)
        self.rect = self.image.get_rect()
        self.width = self.rect[2]
        self.height = self.rect[3]
        self.aspect_ratio = self.width / self.height

    def draw(self, surface, position, alpha):
        width_surface, height_surface = surface.get_size()
        surface_aspect_ratio = width_surface / height_surface

        if surface_aspect_ratio > self.aspect_ratio:
            height = height_surface
            width = int(self.width * height_surface / self.height)
            width_margin = int((width_surface - width) / 2)
            height_margin = 0
        else:
            width = width_surface
            height = int(self.height * width_surface / self.width)
            width_margin = 0
            height_margin = int((height_surface - height) / 2)

        self.rect[0] = width_margin + position[0]
        self.rect[1] = height_margin + position[1]

        image_scaled  = pygame.transform.scale(self.image, (width, height))
        image_scaled.set_alpha(alpha)
        surface.blit(image_scaled, self.rect)

class HalloweenSkeleton():
    def __init__(self):
        self.sprites_lists = {}
        self.idle_image_sprites = None
        self.kinect_initialized = False
        self.last_user_ts = None
        self.last_idle_image_ts = None
        self.last_idle_sprite = None
        self.curr_idle_sprite = None
        self.idle_image_queue = []
        self.idle_image_x = None
        self.idle_image_y = None
        self.idle_image_angle = None
        self.joint_set = None
        self.untracked_user = False

    def get_angle(self, x1, y1, x2, y2):
        return math.atan2(y2 - y1, x2 - x1)

    def load_images(self, user_id):
        self.sprites_lists[user_id] = pygame.sprite.Group()
        for name, data in BODYPART_LIST.items():
            sprite = BodyPart(name, data['joints'], data['coords'])
            self.sprites_lists[user_id].add(sprite)

    def init_kinect(self):
        if self.kinect_initialized:
            self.close_kinect()
            self.kinect_initialized = False

        try:
            openni2.initialize('../KinectLibs/OpenNI-Linux-x64-2.2/Redist')
            dev = openni2.Device.open_any()
        except:
            print('warning: no kinect found.')

        try:
            nite2.initialize('../KinectLibs/NiTE-Linux-x64-2.2/Redist')
            user_tracker = nite2.UserTracker(dev)
            self.kinect_initialized = True
        except utils.NiteError as e:
            print("Unable to start the NiTE human tracker. Check "
                  "the error messages in the console. Model data "
                  "(s.dat, h.dat...) might be inaccessible.")
            print(e)

        return dev, user_tracker

    def close_kinect(self):
        nite2.unload()
        openni2.unload()
        self.kinect_initialized = False

    def get_confidence(self, user):
        if self.joint_set is None:
            self.joint_set = set()
            for name, data in BODYPART_LIST.items():
                for joint in data['joints']:
                    if type(joint) is tuple:
                        for subjoint in joint:
                            self.joint_set.add(subjoint)
                    else:
                        self.joint_set.add(joint)
        total = 0
        count = 0
        for joint in self.joint_set:
            j = user.skeleton.joints[joint]
            total = total + j.positionConfidence
            count = count + 1
        confidence = total / count
        return confidence

    def draw_skeleton(self, surface, user_tracker, user):
        if user.id not in self.sprites_lists:
            self.load_images(user.id)
        self.sprites_lists[user.id].update(user_tracker, user)
        self.sprites_lists[user.id].draw(surface)
        confidence = self.get_confidence(user)
        return confidence

    def set_kinect_angle(self, angle):
        df = subprocess.Popen(['./kinect-tilt', str(angle)], stdout=subprocess.PIPE)
        output = df.communicate()[0].decode('utf-8')
        return output

    '''
    @TODO
    * Add message when person is detect telling them to stand in front of screen
    * Figure out crash with bad magic
    * Overlap fade
    * Have them move and zoom slightly while displayed
    * Other effects: wave, twist, color cycle
    '''
    def draw_idle_images(self, surface):
        if self.idle_image_sprites is None:
            self.idle_image_sprites = pygame.sprite.Group()
            filenames = []
            for extension in ('png', 'jpg', 'jpeg'):
                filenames.extend(glob.glob('images-other/*.' + extension))
            for filename in filenames:
                sprite = IdleImage(filename)
                self.idle_image_sprites.add(sprite)

        if len(self.idle_image_queue) == 0:
            self.idle_image_queue = self.idle_image_sprites.sprites()
            random.shuffle(self.idle_image_queue)

        curr_ts = time.time()
        if self.last_idle_image_ts is None or curr_ts > self.last_idle_image_ts + IDLE_IMAGE_TIMEOUT_S:
            if self.idle_image_angle is not None:
                self.idle_image_angle = (self.idle_image_angle + 90 + random.randint(0, 180)) % 360
            else:
                self.idle_image_angle = random.randint(0,359)
            self.idle_image_direction = self.idle_image_angle * 2 * math.pi / 360
            self.x_last = self.idle_image_x
            self.y_last = self.idle_image_y
            self.x_move = 100 * math.cos(self.idle_image_direction)
            self.y_move = 100 * math.sin(self.idle_image_direction)
            self.last_idle_sprite = self.curr_idle_sprite
            self.curr_idle_sprite = self.idle_image_queue.pop()
            self.last_idle_image_ts = curr_ts

        if curr_ts - self.last_idle_image_ts < FADE_LENGTH_S:
            if self.last_idle_sprite is not None:
                last_alpha = 255 - int(255 * (curr_ts - self.last_idle_image_ts) / FADE_LENGTH_S)
                self.last_idle_sprite.draw(surface, (self.x_last, self.y_last), last_alpha)
            alpha = int(255 * (curr_ts - self.last_idle_image_ts) / FADE_LENGTH_S)
        else:
            alpha = 255

        self.idle_image_x = int(self.x_move * (curr_ts - self.last_idle_image_ts) / IDLE_IMAGE_TIMEOUT_S)
        self.idle_image_y = int(self.y_move * (curr_ts - self.last_idle_image_ts) / IDLE_IMAGE_TIMEOUT_S)
        self.curr_idle_sprite.draw(surface, (self.idle_image_x, self.idle_image_y), alpha)

    def display_fps(self, clock, surface):
        text_to_show = pygame.font.SysFont('Arial', 32).render(str(int(clock.get_fps())), 0, pygame.Color('white'))
        surface.blit(text_to_show, (0, 0))

    def draw_user_message(self, surface):
        message = 'Hi!!! Stand in front of the screen, one person at a time, holding your arms out in a T.'
        text_image = pygame.font.SysFont('Arial', 64).render(message, 0, pygame.Color('white'))
        width_surface, height_surface = surface.get_size()
        width_text, height_text = text_image.get_size()
        width_scaled = int(width_surface * 0.9)
        height_scaled = int(height_text * width_scaled / width_text)
        scaled_text = pygame.transform.scale(text_image, (width_scaled, height_scaled))
        width_background = int(width_surface * 0.95)
        height_background = height_scaled + width_background - width_scaled
        background = pygame.Surface((width_background, height_background))
        background.fill((0, 0, 0))
        x_background = int((width_surface - width_background) / 2)
        y_background = int((height_surface - height_background) / 2)
        surface.blit(background, (x_background, y_background))
        x_text = int((width_surface - width_scaled) / 2)
        y_text = int((height_surface - height_scaled) / 2)
        if MIRRORED:
            surface.blit(scaled_text, (x_text, y_text))
        else:
            flipped_text = pygame.transform.flip(scaled_text, True, False)
            surface.blit(flipped_text, (x_text, y_text))

    def run(self):
        if not DEBUG_NO_KINECT:
            self.set_kinect_angle(KINECT_ANGLE)
            dev, user_tracker = self.init_kinect()
            dev_name = dev.get_device_info().name.decode('UTF-8')
            print("Device Name: {}".format(dev_name))
            use_kinect = False
            if dev_name == 'Kinect':
                use_kinect = True
                print('using Kinect.')
            (kinect_width, kinect_height) = CAPTURE_SIZE_KINECT if use_kinect else CAPTURE_SIZE_OTHERS

        pygame.init()
        pygame.mouse.set_visible(False)
        clock = pygame.time.Clock()

        if FULL_SCREEN:
            display_surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            display_surface = pygame.display.set_mode((WINDOWED_WIDTH, WINDOWED_HEIGHT), 0, 32)

        width_display, height_display = display_surface.get_size()

        ratio = DEPTH_SPACE_WIDTH / DEPTH_SPACE_HEIGHT
        skeleton_surface = pygame.Surface((DEPTH_SPACE_WIDTH, DEPTH_SPACE_HEIGHT))
        idle_image_surface = pygame.Surface((width_display, height_display))
        height_scaled = height_display
        width_scaled = math.floor(height_display * ratio)
        if ASPECT_RATIO > ratio:
            width_margin = int((ASPECT_RATIO * height_display - width_scaled) / 2)
        else:
            width_margin = 0

        running = True
        frame_count = 0
        while running:
            clock.tick(60)

            for event in pygame.event.get():
                if event.type == pygame.KEYDOWN:
                    if event.unicode == 'q' or event.unicode == 'Q':
                        running = False
                        break;
                if event.type == pygame.QUIT:
                    running = False

            user_tracked = False
            if not DEBUG_NO_KINECT:
                skeleton_surface.fill((0, 0, 0))
                if not self.kinect_initialized:
                    dev, user_tracker = self.init_kinect()
                ut_frame = user_tracker.read_frame()
                frame_count = frame_count + 1
                if ut_frame.users:
                    for user in ut_frame.users:
                        if user.is_new():
                            if not user_tracked:
                                self.untracked_user = True
                            self.last_user_ts = time.time()
                            print("{}: new human id:{} detected.".format(frame_count, user.id))
                            user_tracker.start_skeleton_tracking(user.id)
                        elif (user.state == nite2.UserState.NITE_USER_STATE_VISIBLE and
                              user.skeleton.state == nite2.SkeletonState.NITE_SKELETON_TRACKED):
                            self.last_user_ts = time.time()
                            confidence = self.draw_skeleton(skeleton_surface, user_tracker, user)
                            self.untracked_user = False
                            user_tracked = True
                        else:
                            if not user_tracked:
                                self.untracked_user = True
                else:
                    self.untracked_user = False
                    self.last_user_ts = None

                curr_ts = time.time()
                if self.last_user_ts is not None and curr_ts > self.last_user_ts + RESET_TIMEOUT_S:
                    for user in ut_frame.users:
                        user_tracker.stop_skeleton_tracking(user.id)
                    # print('{}: Reset after {} seconds'.format(frame_count, RESET_TIMEOUT_S))
                    self.last_user_ts = None
                    self.close_kinect()

                display_surface.fill((0, 0, 0))
                if MIRRORED:
                    flipped_surface = pygame.transform.flip(skeleton_surface, True, False)
                    scaled_surface = pygame.transform.scale(flipped_surface, (width_scaled, height_scaled))
                else:
                    scaled_surface = pygame.transform.scale(skeleton_surface, (width_scaled, height_scaled))
                display_surface.blit(scaled_surface, (width_margin, 0))

            # @TODO: Seems to be interfering with tracking (CPU utilization?)
            # if self.last_user_ts is None or self.untracked_user:
            if self.last_user_ts is None:
                idle_image_surface.fill((0, 0, 0))
                self.draw_idle_images(idle_image_surface)
                display_surface.blit(idle_image_surface, (0, 0))

            if self.untracked_user:
                self.draw_user_message(display_surface)

            if SHOW_FPS:
                self.display_fps(clock, display_surface)

            pygame.display.flip()

        pygame.quit()
        self.close_kinect()

if __name__ == '__main__':
    skel = HalloweenSkeleton()
    skel.run()
