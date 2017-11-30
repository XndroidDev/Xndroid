#include <jni.h>
#include <sys/socket.h>
#include <stdio.h>
#include <string.h>
#include <sys/un.h>
#include <sys/types.h>
#include <unistd.h>

int send_fd(int sock_fd, int send_fd)
{
    int ret;
    struct msghdr msg;
    struct cmsghdr *p_cmsg;
    struct iovec vec;
    char cmsgbuf[CMSG_SPACE(sizeof(send_fd))];
    int *p_fds;
    char sendchar = '*';
    msg.msg_control = cmsgbuf;
    msg.msg_controllen = sizeof(cmsgbuf);
    p_cmsg = CMSG_FIRSTHDR(&msg);
    p_cmsg->cmsg_level = SOL_SOCKET;
    p_cmsg->cmsg_type = SCM_RIGHTS;
    p_cmsg->cmsg_len = CMSG_LEN(sizeof(send_fd));
    p_fds = (int *)CMSG_DATA(p_cmsg);
    *p_fds = send_fd;

    msg.msg_name = NULL;
    msg.msg_namelen = 0;
    msg.msg_iov = &vec;
    msg.msg_iovlen = 1;
    msg.msg_flags = 0;

    vec.iov_base = &sendchar;
    vec.iov_len = sizeof(sendchar);
    ret = sendmsg(sock_fd, &msg, 0);
    if (ret != 1)
        fflush(stdout);
        return -1;
    return 0;
}

jint Java_net_xndroid_fqrouter_SocksVpnService_createUdpFd( JNIEnv* env, jobject thiz)
{
    return socket(AF_INET, SOCK_DGRAM, 0);
}

jint Java_net_xndroid_fqrouter_SocksVpnService_sendFd( JNIEnv* env, jobject thiz, jint sock_fd, jint fd)
{
	return send_fd(sock_fd, fd);
}

