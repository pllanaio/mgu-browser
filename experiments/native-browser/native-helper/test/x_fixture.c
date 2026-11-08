/* Authored native X11 fixture only; never part of the helper's command API. */
#define _POSIX_C_SOURCE 200809L
#include <X11/Xlib.h>
#include <X11/keysym.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
static void report_state(Display*d,Window root){char keys[32];XQueryKeymap(d,keys);KeySym symbols[]={XK_a,XK_b,XK_c,XK_Shift_L,XK_Control_L,XK_Alt_L,XK_Super_L};int held=0;for(unsigned i=0;i<sizeof(symbols)/sizeof(symbols[0]);i++){unsigned c=XKeysymToKeycode(d,symbols[i]);held+=(keys[c/8]>>(c%8))&1;}Window r,c;int x,y,wx,wy;unsigned mask;XQueryPointer(d,root,&r,&c,&x,&y,&wx,&wy,&mask);printf("STATE %d %u\n",held,mask);fflush(stdout);}
int main(void){Display*d=XOpenDisplay(NULL);if(!d)return 1;int s=DefaultScreen(d);Window root=RootWindow(d,s);Window w=XCreateSimpleWindow(d,root,100,100,500,180,0,0,0xcc3300);XSelectInput(d,w,KeyPressMask|KeyReleaseMask|ButtonPressMask|ButtonReleaseMask|PointerMotionMask|ExposureMask);XStoreName(d,w,"Authored bounded-helper fixture");XMapRaised(d,w);XSetInputFocus(d,w,RevertToParent,CurrentTime);GC gc=XCreateGC(d,w,0,NULL);XSync(d,False);printf("READY 100 100 500 180\n");fflush(stdout);int running=1;unsigned long color=0xcc3300;
while(running){while(XPending(d)){XEvent e;XNextEvent(d,&e);if(e.type==Expose){XSetForeground(d,gc,color);XFillRectangle(d,w,gc,0,0,500,180);XFlush(d);}if(e.type==KeyPress||e.type==KeyRelease)printf("KEY %d %u %u %d\n",e.type,e.xkey.keycode,e.xkey.state,e.xkey.send_event);if(e.type==ButtonPress||e.type==ButtonRelease)printf("BUTTON %d %u %u %d\n",e.type,e.xbutton.button,e.xbutton.state,e.xbutton.send_event);if(e.type==MotionNotify)printf("MOTION %u %d\n",e.xmotion.state,e.xmotion.send_event);fflush(stdout);}struct pollfd p[2]={{ConnectionNumber(d),POLLIN,0},{0,POLLIN,0}};int n=poll(p,2,100);if(n<0)break;if(p[1].revents&POLLIN){char c;if(read(0,&c,1)!=1)break;if(c=='Q')report_state(d,root);else if(c=='R'||c=='G'||c=='B'){color=c=='R'?0xcc3300:c=='G'?0x22bb44:0x1155ee;XSetForeground(d,gc,color);XFillRectangle(d,w,gc,0,0,500,180);XSync(d,False);printf("PAINT %c\n",c);fflush(stdout);}else if(c=='X')running=0;}if(p[1].revents&POLLHUP)break;}
XFreeGC(d,gc);XDestroyWindow(d,w);XCloseDisplay(d);return 0;}
