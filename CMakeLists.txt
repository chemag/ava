cmake_minimum_required(VERSION 3.12)

project(ava VERSION 0.0)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_OSX_ARCHITECTURES "x86_64" CACHE INTERNAL "" FORCE)

# Set compiler flags
set(CMAKE_CXX_FLAGS_DEBUG "-g -O0 -Wall -Wextra -Wno-unused-parameter -Wshadow -Werror")

message(STATUS "CMAKE_CURRENT_SOURCE_DIR: ${CMAKE_CURRENT_SOURCE_DIR} ")


# 1. build external libraries

# 1.1. build libde265 library
add_subdirectory(${CMAKE_SOURCE_DIR}/lib/libde265)


# 2. build libava library
add_library(ava src/libava.cc)

target_link_libraries(ava
  libde265
)

target_include_directories(ava
  PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/lib/libde265/libde265
)
