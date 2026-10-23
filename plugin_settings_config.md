<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<settings version="1">
  <section id="plugin.video.telugulive">
    <category id="general" label="30000">
      <group id="1">
        <setting id="playlist_url" type="string" label="30001">
          <level>0</level>
          <default>{{BASE_URL}}/telugu.m3u</default>
          <control type="edit" format="string">
            <heading>30001</heading>
          </control>
        </setting>
      </group>
    </category>
    <category id="jio" label="30002">
      <group id="2">
        <setting id="jio_mobile" type="string" label="30003">
          <level>0</level>
          <default></default>
          <control type="edit" format="string">
            <heading>30003</heading>
          </control>
        </setting>
        <setting id="jio_token" type="string" label="30004">
          <level>0</level>
          <default></default>
          <control type="edit" format="string">
            <heading>30004</heading>
          </control>
        </setting>
      </group>
    </category>
  </section>
</settings>