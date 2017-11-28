LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)

LOCAL_MODULE    := sockvpn
LOCAL_SRC_FILES := sockvpn.c

include $(BUILD_SHARED_LIBRARY)