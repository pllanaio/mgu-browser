#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <X11/extensions/XShm.h>
/* Stable libXtst API declarations; XTest.h also pulls unrelated XInput development headers. */
extern Bool XTestFakeKeyEvent(Display*, unsigned int, Bool, unsigned long);
extern Bool XTestFakeButtonEvent(Display*, unsigned int, Bool, unsigned long);
extern Bool XTestFakeMotionEvent(Display*, int, int, int, unsigned long);
#include <sys/ipc.h>
#include <sys/shm.h>
#include <time.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int xerrors;
static int onerror(Display *d, XErrorEvent *e) {(void)d;(void)e;xerrors++;return 0;}
static double now(void) {struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9;}
static void pause_ms(int ms) {struct timespec t={ms/1000,(ms%1000)*1000000L};nanosleep(&t,NULL);}
static uint32_t checksum(const unsigned char *p,size_t n) {uint32_t h=2166136261U;for(size_t i=0;i<n;i++)h=(h^p[i])*16777619U;return h;}
int main(int argc,char **argv) {
 (void)argc;const char *state=argv[1];Display *d=XOpenDisplay(NULL);if(!d){fprintf(stderr,"Private XOpenDisplay failed\n");return 1;}
 XSetErrorHandler(onerror);int s=DefaultScreen(d);Window root=RootWindow(d,s);int width=DisplayWidth(d,s),height=DisplayHeight(d,s);int op,ev,err;
 int mit=XShmQueryExtension(d),xtest=XQueryExtension(d,"XTEST",&op,&ev,&err),damage=XQueryExtension(d,"DAMAGE",&op,&ev,&err),randr=XQueryExtension(d,"RANDR",&op,&ev,&err);
 Window w=XCreateSimpleWindow(d,root,80,80,500,140,1,0,0xffffff);XStoreName(d,w,"MGU private native input and SHM fixture");XSelectInput(d,w,KeyPressMask|KeyReleaseMask|ButtonPressMask|ButtonReleaseMask|PointerMotionMask|ExposureMask|FocusChangeMask);XMapRaised(d,w);XSync(d,False);pause_ms(250);XSetInputFocus(d,w,RevertToParent,CurrentTime);XSync(d,False);
 while(XPending(d)){XEvent e;XNextEvent(d,&e);}
 unsigned int tab=XKeysymToKeycode(d,XK_Tab),shift=XKeysymToKeycode(d,XK_Shift_L),a=XKeysymToKeycode(d,XK_a);
 XTestFakeKeyEvent(d,tab,True,0);XTestFakeKeyEvent(d,tab,False,0);XTestFakeKeyEvent(d,shift,True,0);XTestFakeKeyEvent(d,tab,True,0);XTestFakeKeyEvent(d,tab,False,0);XTestFakeKeyEvent(d,shift,False,0);XTestFakeKeyEvent(d,a,True,0);XTestFakeKeyEvent(d,a,False,0);
 Window child;int wx,wy;XTranslateCoordinates(d,w,root,0,0,&wx,&wy,&child);XTestFakeMotionEvent(d,-1,wx+40,wy+40,0);XTestFakeButtonEvent(d,1,True,0);XTestFakeButtonEvent(d,1,False,0);XSync(d,False);pause_ms(100);
 int keys=0,releases=0,tabs=0,shift_tabs=0,letters=0,buttons=0,button_releases=0,motion=0;
 while(XPending(d)){XEvent e;XNextEvent(d,&e);if(e.type==KeyPress){keys++;if(e.xkey.keycode==tab){tabs++;if(e.xkey.state&ShiftMask)shift_tabs++;}if(e.xkey.keycode==a)letters++;}if(e.type==KeyRelease)releases++;if(e.type==ButtonPress)buttons++;if(e.type==ButtonRelease)button_releases++;if(e.type==MotionNotify)motion++;}
 XShmSegmentInfo info={0};XImage *im=XShmCreateImage(d,DefaultVisual(d,s),DefaultDepth(d,s),ZPixmap,NULL,&info,width,height);if(!im)return 2;
 size_t bytes=(size_t)im->bytes_per_line*height;info.shmid=shmget(IPC_PRIVATE,bytes,IPC_CREAT|0600);if(info.shmid<0){perror("shmget");return 3;}info.shmaddr=shmat(info.shmid,NULL,0);if(info.shmaddr==(char*)-1){perror("shmat");shmctl(info.shmid,IPC_RMID,NULL);return 4;}im->data=info.shmaddr;info.readOnly=False;int attached=XShmAttach(d,&info);XSync(d,False);shmctl(info.shmid,IPC_RMID,NULL);
 GC gc=XCreateGC(d,w,0,NULL);uint32_t previous=0;int changed=0,frames=0;double start=now(),max_ms=0,sum_ms=0;
 for(int i=0;i<60;i++){XSetForeground(d,gc,(i&1)?0x1468ad:0xda9b32);XFillRectangle(d,w,gc,0,0,500,140);XSync(d,False);double t=now();if(!XShmGetImage(d,root,im,0,0,AllPlanes))break;uint32_t value=checksum((unsigned char*)im->data,bytes);double ms=(now()-t)*1000;if(ms>max_ms)max_ms=ms;sum_ms+=ms;changed+=i==0||value!=previous;previous=value;frames++;double remaining=start+(i+1)/30.0-now();if(remaining>0){struct timespec ts={(time_t)remaining,(long)((remaining-(time_t)remaining)*1e9)};nanosleep(&ts,NULL);}}
 double elapsed=now()-start;char path[4096];snprintf(path,sizeof(path),"%s/probe-maps.txt",state);FILE *maps=fopen("/proc/self/maps","r"),*out=fopen(path,"w");if(maps&&out){char b[4096];while(fgets(b,sizeof(b),maps))fputs(b,out);}if(maps)fclose(maps);if(out)fclose(out);
 int ok=width==1280&&height==400&&mit&&xtest&&damage&&randr&&keys==4&&releases==4&&tabs==2&&shift_tabs==1&&letters==1&&buttons==1&&button_releases==1&&motion>=1&&attached&&frames==60&&changed==60&&xerrors==0;
 printf("{\"success\":%s,\"uid\":%d,\"width\":%d,\"height\":%d,\"mitShm\":%s,\"xTest\":%s,\"damage\":%s,\"randr\":%s,\"keyPress\":%d,\"keyRelease\":%d,\"tabPress\":%d,\"shiftTabPress\":%d,\"letterPress\":%d,\"buttonPress\":%d,\"buttonRelease\":%d,\"motion\":%d,\"frames\":%d,\"changedFrames\":%d,\"elapsedSeconds\":%.6f,\"captureFps\":%.3f,\"captureCrcMeanMs\":%.3f,\"captureCrcMaxMs\":%.3f,\"xErrors\":%d}\n",ok?"true":"false",getuid(),width,height,mit?"true":"false",xtest?"true":"false",damage?"true":"false",randr?"true":"false",keys,releases,tabs,shift_tabs,letters,buttons,button_releases,motion,frames,changed,elapsed,frames/elapsed,sum_ms/(frames?frames:1),max_ms,xerrors);
 XShmDetach(d,&info);XSync(d,False);im->data=NULL;XDestroyImage(im);shmdt(info.shmaddr);XFreeGC(d,gc);XDestroyWindow(d,w);XCloseDisplay(d);return ok?0:1;
}
