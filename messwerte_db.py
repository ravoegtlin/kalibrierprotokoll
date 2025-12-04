# coding: utf-8
from typing import List

from sqlalchemy.orm import declarative_base
from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Time, Date
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy import PickleType
from sqlalchemy.orm import relationship, Mapped, sessionmaker, column_property
from sqlalchemy import func
from sqlalchemy import Table, MetaData
from datetime import date

#engine = create_engine('mssql+pymssql://SQL_U_KS04:RchtzKS0421#!@10.111.10.16:1433/KS05_DEV_BACKUP')
engine = create_engine('mssql+pymssql://sa:Dhbfeb21479863!11@10.111.10.66:1433/KS05')
Base = declarative_base()

def anlegen():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    #metadata = MetaData()
    #table = Table('kalibrierung', metadata, autoload_with=engine)
    #table.drop(engine)
    #table.create(engine)

class Kalibrierung(Base):
    __tablename__ = 'kalibrierung'
    uid = Column(Integer, primary_key=True)
    date = Column(DateTime, server_default=func.now())
    #kalibrierlauf_23 = relationship("Kalibrierlauf", back_populates="kalibrierung", uselist=False)
    #kalibrierlauf_40 = relationship("Kalibrierlauf", back_populates="kalibrierung", uselist=False)
    kalibrierlauf_lecktest_id = Column(Integer, ForeignKey('kalibrierlauf.uid'), nullable=False)
    temperierung_23_id = Column(Integer, ForeignKey('kalibrierlauf.uid'), nullable=False)
    kalibrierlauf_23_id = Column(Integer, ForeignKey('kalibrierlauf.uid'), nullable=False)
    temperierung_40_id = Column(Integer, ForeignKey('kalibrierlauf.uid'), nullable=False)
    kalibrierlauf_40_id = Column(Integer, ForeignKey('kalibrierlauf.uid'), nullable=False)
    temperierung_verify_id = Column(Integer, ForeignKey('kalibrierlauf.uid'), nullable=False)
    kalibrierlauf_verify_id = Column(Integer, ForeignKey('kalibrierlauf.uid'), nullable=False)
    lookup_id = Column(Integer, ForeignKey('lookup.uid'), nullable=True)

    lookups = relationship("Lookup", foreign_keys="[Lookup.kalibrierung_id]")
    kalibrierlauf_lecktest = relationship("Kalibrierlauf", foreign_keys=[kalibrierlauf_lecktest_id])
    temperierung_23 = relationship("Kalibrierlauf", foreign_keys=[temperierung_23_id])
    kalibrierlauf_23 = relationship("Kalibrierlauf", foreign_keys=[kalibrierlauf_23_id])
    temperierung_40 = relationship("Kalibrierlauf", foreign_keys=[temperierung_40_id])
    kalibrierlauf_40 = relationship("Kalibrierlauf", foreign_keys=[kalibrierlauf_40_id])
    temperierung_verify = relationship("Kalibrierlauf", foreign_keys=[temperierung_verify_id])
    kalibrierlauf_verify = relationship("Kalibrierlauf", foreign_keys=[kalibrierlauf_verify_id])
    #lookup = relationship("Lookup", foreign_keys=[lookup_id])

class Kalibrierlauf(Base):
    __tablename__ = 'kalibrierlauf'
    uid = Column(Integer, primary_key=True)
    dat_file_sektions_nr = Column(Integer, default=-1)
    date = Column(DateTime, server_default=func.now())
    operator_name = Column(String, default='KS05')
    batch = Column(String, default='2023-15-03-00')
    samples = Column(Integer, default=0)
    gas = Column(String, default='Air')
    gas_total = Column(String, default='unknown')
    mode = Column(String, default='Ticks')
    gain = Column(Integer, default=0)
    heat_power = Column(Integer, default=1)
    set_temp = Column(Float, default=23.0)
    messpunkte = relationship('Messpunkt', backref='kalibrierlauf')
    last_exported_tag = Column(Integer, default=0)  # Speichert die letzte exportierte DataTag Nummer

class Lookup(Base):
    __tablename__ = 'lookup'  # Name der Tabelle
    uid = Column(Integer, primary_key=True)  # Primärschlüssel
    seriennummer = Column(String, nullable=True)
    date = Column(Date, server_default=func.now())
    time = Column(Time, server_default=func.now())
    user = Column(String, nullable=True )  # User
    dat_file_sektions_nr = Column(Integer, default=-1)
    dat_file_sektions_nr_23 = Column(Integer, default=-1)
    dat_file_sektions_nr_40 = Column(Integer, default=-1)
    dat_file_sektions_nr_verify = Column(Integer, default=-1)
    kalibrierung_vollständig_exportiert = Column(Boolean, default=False)

    lookup_ident = Column(Integer, nullable=True )  # LookupIdent als Integer
    lookup_info = Column(Integer, nullable=True )  # LookupInfo als Integer
    sensor_id = Column(Integer, nullable=True )  # SensorId als Integer
    calculation = Column(String, nullable=True )  # Berechnung (z. B. Lookup standard)
    sw_version = Column(String, nullable=True )  # SW_Version
    cal_unit = Column(String, nullable=True )  # CalUnit

    # Flow-Parameter
    flow_range = Column(Float, nullable=True )  # FlowRange
    cal_max_flow = Column(Float, nullable=True )  # CalMaxFlow
    flow_unit = Column(String, nullable=True )  # FlowUnit (z. B. ln/min)

    # Gas-Parameter
    gas_name = Column(String, nullable=True )  # GasName (z. B. Air)
    gas = Column(String, nullable=True )  # Gas (z. B. Air)

    # Druck und Temperatur
    ref_pressure = Column(Float, nullable=True )  # RefPressure
    ref_temp = Column(Float, nullable=True )  # RefTemp
    density = Column(Float, nullable=True )  # Density

    # Offset-Werte
    offset_k0 = Column(Float, nullable=True )  # Offset_k0
    offset_k1 = Column(Float, nullable=True )  # Offset_k1
    offset_komp_k0 = Column(Float, nullable=True )  # OffsetKomp_k0
    offset_komp_k1 = Column(Float, nullable=True )  # OffsetKomp_k1

    # Weitere Kalibrierwerte
    gain = Column(Float, nullable=True )  # Gain
    heat_power = Column(Float, nullable=True )  # HeatPower
    dynamic = Column(Integer, nullable=True )  # Dynamic (0 oder 1)
    cut_off = Column(Float, nullable=True )  # CutOff
    temp_calib = Column(Float, nullable=True )  # TempCalib
    temp_operate = Column(Float, nullable=True )  # TempOperate
    calib_pressure = Column(Float, nullable=True )  # CalibPressure
    pressure_in = Column(Float, nullable=True )  # PressureIn
    pressure_out = Column(Float, nullable=True )  # PressureOut

    kn_sccm_org = Column(Float, nullable=True )  # Pkn_sccm_org
    kn_sccm = Column(Float, nullable=True )  # kn_sccm
    kn_unit = Column(String, nullable=True )  # kn_Unit
    kn_scale = Column(Float, nullable=True )  # kn_Scale

    # Temperatur-Offsets
    temp_k0 = Column(Float, nullable=True )  # Temp_k0
    temp_k1 = Column(Float, nullable=True )  # Temp_k1

    # Lookup-Ticks und FlowTicks
    flow_ticks_0x4000 = Column(MutableList.as_mutable(PickleType), default=[])
    dut_messungen = Column(MutableList.as_mutable(PickleType), default=[])
    flow_ticks_0xC000 = Column(MutableList.as_mutable(PickleType), default=[])
    lookup_ticks = Column(MutableList.as_mutable(PickleType), default=[])

    # Beziehung zu Kalibrierung
    kalibrierung_id = Column(Integer, ForeignKey('kalibrierung.uid'), nullable=False)

    def __repr__(self):
        return f'<Lookup {self.lookup_ident}>'


class Messung(Base):
    __tablename__ = 'messungen'
    uid = Column(Integer, primary_key=True)
    wert = Column(Float)


class Messpunkt(Base):
    __tablename__ = 'messpunkt'
    uid = Column(Integer, primary_key=True)
    temp_in = Column(Float, default=0.0)
    temp_out = Column(Float, default=0.0)
    temp_amb = Column(Float, default=0.0)
    pressure_in = Column(Float, default=0.0)
    pressure_out = Column(Float, default=0.0)
    pressure_amb = Column(Float, default=0.0)
    humidity = Column(Float, default=0.0)
    flow_ref = Column(Float, default=0.0)
    set_flow = Column(Float, default=0.0)
    ref_used = Column(String, default=0.0)
    sigma_flow_ref = Column(Float, default=0.0)
    dut_messungen = relationship('DutMessung', backref='messpunkt')
    lauf_id = Column(Integer, ForeignKey('kalibrierlauf.uid'), nullable=False)

class DutMessung(Base):
    __tablename__ = 'dut_messung'
    uid = Column(Integer, primary_key=True)
    seriennummer = Column(Integer, default='0')
    flow_device = Column(Float, default=0.0)
    temp_device = Column(Float, default=0.0)
    sigma_flow_device = Column(Float, default=0.0)
    sigma_temp_device = Column(Float, default=0.0)
    messpunkt_id = Column(Integer, ForeignKey('messpunkt.uid'), nullable=False)


#    def speichern(self, werte):
#        if werte:
#            Session = sessionmaker(bind=engine)
#            session = Session()
#            wert = Messwerte()
#            for key in werte:
#                setattr(wert, key, werte[key])
#            session.add(wert)
#            session.commit()

if __name__ == "__main__":
    anlegen()
#    Session = sessionmaker(bind=engine)
#    session = Session()
#    test_zeile = Kalibrierung()
#    test_zeile.test = 1
#    test_zeile.kalibrierlauf_23 = Kalibrierlauf()
#    test_zeile.kalibrierlauf_40 = Kalibrierlauf()
#    test_zeile.kalibrierlauf_verify = Kalibrierlauf()
#    session.add(test_zeile)
#    session.commit()
