#include <pthread.h>
#include <iostream>

void* start_routine(void* args)
{
  return args;
}

int main(int argc, char *argv[])
{
  /* This is a compile and link test, no code to actually run things. */
  /*pthread_t thread;
  pthread_create(&thread, 0, start_routine, 0);
  pthread_join(thread, 0);*/

  std::cout << "Hello world!" << std::endl;

  return 0;
}