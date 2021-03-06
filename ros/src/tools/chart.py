#!/usr/bin/env python
import matplotlib
matplotlib.use('TkAgg')  # Needs to be done before importing pyplot

import rospy
from geometry_msgs.msg import PoseStamped
from styx_msgs.msg import Lane, TrafficLightArray
from matplotlib import pyplot as plt
from threading import Lock
import copy
import itertools


class Chart(object):
    """
    The ROS node charts the track, the current car position and its current path
    """
    def __init__(self):
        rospy.init_node('chart', log_level=rospy.DEBUG)

        plt.ion()  # Necessary to ensure matplotlib will not block after showing the image

        self.fig, self.ax = plt.subplots()

        # The track waypoints to be charted, i.e. the /base_waypoints
        self.waypoints = []
        self.waypoints_lock = Lock()

        # The car pose
        self.pose = None
        self.is_pose_updated = False
        self.pose_lock = Lock()

        # The car path, i.e. the /final_waypoints
        self.path = []
        self.is_path_updated = False
        self.path_lock = Lock()

        # The traffic lights, status and coordinates, i.e. the /vehicle/traffic_lights coming from the simulator
        self.traffic_lights = None
        self.traffic_lights_lock = Lock()

        # Subscription to /current_pose, /final_waypoints and /vehicle/traffic_lights happens in waypoints_cb
        rospy.Subscriber('/base_waypoints', Lane, self.waypoints_cb)

        self.loop()

    def get_waypoints(self):
        self.waypoints_lock.acquire()
        wps = self.waypoints
        self.waypoints_lock.release()
        return wps

    def pose_updated(self):
        self.pose_lock.acquire()
        result = self.is_pose_updated
        self.pose_lock.release()
        return result

    def get_pose(self):
        self.pose_lock.acquire()
        result = copy.deepcopy(self.pose)
        self.is_pose_updated = False
        self.pose_lock.release()
        return result

    def get_path(self):
        self.path_lock.acquire()
        path = copy.deepcopy(self.path)
        self.is_path_updated = False
        self.path_lock.release()
        return path

    def path_updated(self):
        self.path_lock.acquire()
        updated = self.is_path_updated
        self.path_lock.release()
        return updated

    def get_traffic_lights(self):
        self.traffic_lights_lock.acquire()
        tls = copy.deepcopy(self.traffic_lights)
        self.traffic_lights_lock.release()
        return tls

    def loop(self):
        rate = rospy.Rate(5)  # The chart refresh rate, no need for it to be stupid high

        # Wait to receive the track waypoints, can't chart anything before that
        waypoints=[]
        while not rospy.is_shutdown() and len(waypoints) == 0:
            waypoints = self.get_waypoints()
            rate.sleep()

        # Stick them in w_x and w_y, and make the first drawing of the track
        w_x, w_y = [], []
        for waypoint in waypoints:
            w_x.append(waypoint.pose.pose.position.x)
            w_y.append(waypoint.pose.pose.position.y)
        self.ax.plot(w_x, w_y, 'b')
        plt.show()

        # Process updates in the car pose and its path
        first_iter = True
        first_path_iter = True
        update_chart = True
        first_tl_iter = True
        tl_marker = ('ro','yo', 'go', 'bo')
        while not rospy.is_shutdown():
            # Update the car pose
            if self.pose_updated():
                x, y = self.get_pose()
                if first_iter:
                    car_dot, = self.ax.plot(x, y, 'ko')
                    first_iter = False
                else:
                    car_dot.set_ydata(y)
                    car_dot.set_xdata(x)
                update_chart = True
            # Update the path
            if self.path_updated():
                path = self.get_path()
                path_wp_x, path_wp_y = [], []
                for wp in path:
                    path_wp_x.append(wp.pose.pose.position.x)
                    path_wp_y.append(wp.pose.pose.position.y)
                    if first_path_iter:
                        path_line, = self.ax.plot(path_wp_x, path_wp_y, 'm', linewidth=3.)
                        first_path_iter = False
                    else:
                        path_line.set_ydata(path_wp_y)
                        path_line.set_xdata(path_wp_x)
                    update_chart = True
            # Update the traffic lights
            if self.traffic_lights is not None:
                tls = self.get_traffic_lights()
                tl_x, tl_y, tl_c = [], [], []
                for tl in tls:
                    tl_x.append(tl[0])
                    tl_y.append(tl[1])
                    tl_c.append(tl_marker[tl[2]])
                marker = itertools.cycle(tl_c)
                if first_tl_iter:
                    tl_dots, = self.ax.plot(tl_x, tl_y, marker.next())
                    first_tl_iter = False
                    update_chart = True
                else:
                    tl_dots.set_markerfacecolor(marker.next()[0])
                    tl_dots.set_markeredgecolor(marker.next()[0])
                    update_chart = True
            # If any update was applied to the chart, then redraw it
            if update_chart:
                self.fig.canvas.draw()
                plt.pause(0.001)  # Give matplotlib a chance to redraw, and resize the window if required by the user
                update_chart = False
            rate.sleep()

    def waypoints_cb(self, waypoints):
        assert len(self.waypoints) == 0
        self.waypoints_lock.acquire()
        self.waypoints = waypoints.waypoints
        self.waypoints_lock.release()
        rospy.logdebug('Received {} waypoints:'.format(len(waypoints.waypoints)))
        rospy.Subscriber('/current_pose', PoseStamped, self.pose_cb)
        rospy.Subscriber('/final_waypoints', Lane, self.path_cb)
        rospy.Subscriber('/vehicle/traffic_lights', TrafficLightArray , self.traffic_lights_cb)


    def pose_cb(self, msg):
        self.pose_lock.acquire()
        x = msg.pose.position.x
        y = msg.pose.position.y
        self.pose = x, y
        self.is_pose_updated = True
        self.pose_lock.release()

    def path_cb(self, msg):
        self.path_lock.acquire()
        self.path = msg.waypoints
        self.is_path_updated = True
        self.path_lock.release()

    def traffic_lights_cb(self, msg):
        self.traffic_lights_lock.acquire()
        self.traffic_lights = []
        for tl in msg.lights:
            self.traffic_lights.append((tl.pose.pose.position.x, tl.pose.pose.position.y, tl.state))
        self.traffic_lights_lock.release()

if __name__ == '__main__':
    try:
        Chart()
    except rospy.ROSInterruptException:
        rospy.logerr('Could not start chart node.')
