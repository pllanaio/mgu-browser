#define _GNU_SOURCE
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>
#include <poll.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#define MAX (256u*1024u)
static int transfer(int from,int to){uint32_t n;unsigned char head[4],data[8192];size_t got=0;while(got<4){ssize_t r=read(from,head+got,4-got);if(r<=0)return -1;got+=(size_t)r;}n=(uint32_t)head[0]|(uint32_t)head[1]<<8|(uint32_t)head[2]<<16|(uint32_t)head[3]<<24;if(!n||n>MAX)return -1;size_t w=0;while(w<4){ssize_t r=write(to,head+w,4-w);if(r<=0)return -1;w+=(size_t)r;}while(n){size_t want=n<sizeof(data)?n:sizeof(data);ssize_t r=read(from,data,want);if(r<=0)return -1;w=0;while(w<(size_t)r){ssize_t a=write(to,data+w,(size_t)r-w);if(a<=0)return -1;w+=(size_t)a;}n-=(uint32_t)r;}return 0;}
int main(int argc,char**argv){if(argc<2||strcmp(argv[1],"chrome-extension://cioniecfpnfdjfkfhcijhdpjabcpbplj/"))return 2;int s=socket(AF_UNIX,SOCK_STREAM|SOCK_CLOEXEC,0);struct sockaddr_un a={.sun_family=AF_UNIX};strcpy(a.sun_path,"/tmp/mgu-native-extension-prototype/state/native.sock");if(s<0||connect(s,(struct sockaddr*)&a,sizeof(a)))return 3;struct ucred c;socklen_t n=sizeof(c);if(getsockopt(s,SOL_SOCKET,SO_PEERCRED,&c,&n)||n!=sizeof(c)||c.uid!=getuid())return 4;struct pollfd p[2]={{.fd=0,.events=POLLIN},{.fd=s,.events=POLLIN}};while(poll(p,2,-1)>0){if(p[0].revents&POLLIN){if(transfer(0,s))break;}if(p[1].revents&POLLIN){if(transfer(s,1))break;}if(p[0].revents&(POLLHUP|POLLERR|POLLNVAL)||p[1].revents&(POLLHUP|POLLERR|POLLNVAL))break;}close(s);return 0;}
